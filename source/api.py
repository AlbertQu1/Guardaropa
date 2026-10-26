"""
Backend de Guardarropa.

Uso:
    uvicorn source.api:app --host 0.0.0.0 --port 8003 --reload
"""

import asyncio
import os
import threading

import numpy as np
from dataclasses import asdict

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

import params
from source import fotos
from source.db import conexion
from source.embeddings_client import embed
from source.ia import get_provider

load_dotenv()
S = params.DB_SCHEMA

app = FastAPI(title="Guardarropa API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for sub in ("originales", "recortes", "usuario", "tryon"):
    os.makedirs(os.path.join(params.MEDIA_DIR, sub), exist_ok=True)
app.mount("/media", StaticFiles(directory=params.MEDIA_DIR), name="media")


@app.on_event("startup")
def precargar_rembg():
    # Cargar el modelo tarda ~50s en este CPU: se hace en segundo plano al arrancar.
    threading.Thread(target=fotos._rembg, daemon=True).start()

COLUMNAS = ["id", "foto_original", "foto_recortada", "categoria", "subcategoria", "colores", "estampado",
            "material", "formalidad", "temporada", "ocasiones", "descripcion", "ultimo_uso", "veces_usada"]


class PrendaIn(BaseModel):
    foto_original: str
    foto_recortada: str | None = None
    categoria: str
    subcategoria: str | None = None
    colores: list[str] = []
    estampado: str | None = None
    material: str | None = None
    formalidad: int | None = Field(default=None, ge=1, le=5)
    temporada: list[str] = []
    ocasiones: list[str] = []
    descripcion: str = ""


def _texto_embedding(p: PrendaIn) -> str:
    partes = [p.subcategoria or p.categoria, " ".join(p.colores), p.estampado or "", p.material or "", p.descripcion]
    return ". ".join(x for x in partes if x)


def _validar_ruta(ruta: str | None):
    if ruta and (".." in ruta or not os.path.isfile(os.path.join(params.MEDIA_DIR, ruta))):
        raise HTTPException(400, f"Foto no encontrada: {ruta}")


@app.get("/health")
def health():
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {S}.prendas WHERE activa")
        prendas = cur.fetchone()[0]
    return {"ok": True, "prendas": prendas, "ia_provider": os.environ.get("IA_PROVIDER", "gemini")}


@app.post("/prendas/analizar")
async def analizar(foto: UploadFile = File(...)):
    """Guarda la foto, recorta el fondo y pide etiquetas a la IA. No inserta nada:
    la app muestra las etiquetas para confirmar y luego llama a POST /prendas."""
    datos = await foto.read()
    try:
        img = fotos.normalizar(datos)
    except Exception:
        raise HTTPException(400, "No pude leer la imagen")
    original = fotos.guardar_original(img)
    # Recorte (CPU local) y etiquetado (Gemini) en paralelo.
    recorte, etiquetas = await asyncio.gather(
        run_in_threadpool(fotos.recortar_fondo, img),
        run_in_threadpool(get_provider().etiquetar_prenda, fotos.a_jpeg_bytes(img), "image/jpeg"),
        return_exceptions=True,
    )
    if isinstance(recorte, Exception):
        print(f"recortar_fondo fallo: {recorte}")
        recorte = None
    if isinstance(etiquetas, Exception):  # sin IA igual se puede capturar a mano
        print(f"etiquetar_prenda fallo: {etiquetas}")
        etiquetas = None
    else:
        etiquetas = asdict(etiquetas)
    return {"foto_original": original, "foto_recortada": recorte, "etiquetas": etiquetas}


@app.post("/prendas")
def crear_prenda(p: PrendaIn):
    if p.categoria not in params.CATEGORIAS:
        raise HTTPException(400, f"Categoria invalida: {p.categoria}")
    _validar_ruta(p.foto_original)
    _validar_ruta(p.foto_recortada)
    vector = np.array(embed([_texto_embedding(p)])[0])
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {S}.prendas (foto_original, foto_recortada, categoria, subcategoria, colores, estampado,
                    material, formalidad, temporada, ocasiones, descripcion, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector) RETURNING id""",
            (p.foto_original, p.foto_recortada, p.categoria, p.subcategoria, p.colores, p.estampado, p.material,
             p.formalidad, p.temporada, p.ocasiones, p.descripcion, vector),
        )
        return {"id": cur.fetchone()[0]}


@app.get("/prendas")
def listar_prendas(categoria: str | None = None):
    sql = f"SELECT {', '.join(COLUMNAS)} FROM {S}.v_prendas_uso"
    args: list = []
    if categoria:
        sql += " WHERE categoria = %s"
        args.append(categoria)
    sql += " ORDER BY created_at DESC"
    with conexion() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchall()


@app.put("/prendas/{prenda_id}")
def editar_prenda(prenda_id: int, p: PrendaIn):
    if p.categoria not in params.CATEGORIAS:
        raise HTTPException(400, f"Categoria invalida: {p.categoria}")
    vector = np.array(embed([_texto_embedding(p)])[0])
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {S}.prendas SET categoria=%s, subcategoria=%s, colores=%s, estampado=%s, material=%s,
                    formalidad=%s, temporada=%s, ocasiones=%s, descripcion=%s, embedding=%s::vector
                WHERE id=%s AND activa""",
            (p.categoria, p.subcategoria, p.colores, p.estampado, p.material, p.formalidad, p.temporada,
             p.ocasiones, p.descripcion, vector, prenda_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Prenda no encontrada")
    return {"ok": True}


@app.delete("/prendas/{prenda_id}")
def baja_prenda(prenda_id: int):
    """Baja logica: la prenda deja de aparecer pero se conserva su historial de usos."""
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE {S}.prendas SET activa = FALSE WHERE id = %s", (prenda_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Prenda no encontrada")
    return {"ok": True}
