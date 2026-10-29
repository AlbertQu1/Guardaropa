"""
Backend de Guardarropa.

Uso:
    uvicorn source.api:app --host 0.0.0.0 --port 8003 --reload
"""

import asyncio
import os
import re
import threading
import time
from typing import Literal

import numpy as np
from dataclasses import asdict
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, Field

import params
from source import combinador, fotos, guia_cuidado, lavanderia, simbolos_cuidado
from source.db import conexion
from source.embeddings_client import embed
from source.ia import get_provider

load_dotenv()
S = params.DB_SCHEMA

app = FastAPI(title="Guardarropa API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for sub in ("originales", "recortes", "etiquetas", "usuario", "tryon", fotos.TEMPORAL):
    os.makedirs(os.path.join(params.MEDIA_DIR, sub), exist_ok=True)
app.mount("/media", StaticFiles(directory=params.MEDIA_DIR), name="media")


@app.on_event("startup")
def precargar_rembg():
    # Cargar el modelo tarda ~50s en este CPU: se hace en segundo plano al arrancar.
    threading.Thread(target=fotos._rembg, daemon=True).start()


def limpiar_fotos() -> dict:
    """Borra fotos analizadas que nunca se confirmaron y fotos que ya no usa ninguna prenda."""
    rutas_en_uso = None
    # Solo con el schema real: con un schema de pruebas, las fotos reales parecerian huerfanas
    if S == "guardarropa":
        with conexion() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT unnest(ARRAY[foto_original, foto_recortada, foto_etiqueta])
                            FROM {S}.prendas""")  # incluye las que salieron del closet (Salidas muestra su foto)
            rutas_en_uso = {r[0] for r in cur.fetchall() if r[0]}
    return fotos.limpiar(rutas_en_uso, params.HORAS_FOTO_TEMPORAL)


def _ciclo_limpieza():
    while True:
        try:
            r = limpiar_fotos()
            if r["temporales"] or r["huerfanas"]:
                print(f"limpieza de fotos: {r}")
        except Exception as e:  # nunca tumbar la API por la limpieza
            print(f"limpieza de fotos fallo: {e}")
        time.sleep(params.HORAS_ENTRE_LIMPIEZAS * 3600)


@app.on_event("startup")
def iniciar_limpieza():
    threading.Thread(target=_ciclo_limpieza, daemon=True).start()


class DescartarIn(BaseModel):
    rutas: list[str]


@app.post("/temporal/descartar")
def descartar_temporal(d: DescartarIn):
    """La app avisa que el usuario cancelo: se borran sus fotos temporales en ese momento."""
    return {"borradas": fotos.descartar(d.rutas)}

COLUMNAS = ["id", "foto_original", "foto_recortada", "categoria", "subcategoria", "colores", "estampado",
            "material", "formalidad", "temporada", "ocasiones", "descripcion", "foto_etiqueta", "composicion",
            "cuidado", "talla", "marca", "ajuste", "ultimo_uso", "veces_usada"]


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
    talla: str | None = None
    marca: str | None = None
    ajuste: str | None = None

    def normalizar(self):
        """Talla en mayusculas ('m' -> 'M', '32 x 30' -> '32X30'); vacios -> None."""
        self.talla = normalizar_talla(self.talla)
        self.marca = " ".join((self.marca or "").split()) or None
        self.ajuste = self.ajuste or None
        if self.ajuste and self.ajuste not in params.AJUSTES:
            raise HTTPException(400, f"Ajuste invalido: {self.ajuste}")


def normalizar_talla(t: str | None) -> str | None:
    """'m' -> 'M'; '32 x 30' / '32X30' -> '32/30' (cintura/largo); '15½ 32/33' -> '15.5/32-33' (cuello/manga)."""
    t = (t or "").strip().upper().replace("½", ".5").replace(",", ".")
    if not t:
        return None
    t = re.sub(r"(\d)\s*[X×]\s*(\d)", r"\1/\2", t)
    # cuello y manga: '15.5 32/33' -> dos medidas, la manga como rango
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*[/ ]\s*(\d+)\s*[/-]\s*(\d+)", t)
    if m:
        return f"{m[1]}/{m[2]}-{m[3]}"
    return re.sub(r"\s*/\s*", "/", re.sub(r"\s+", " ", t))


def _texto_embedding(p: PrendaIn) -> str:
    partes = [p.subcategoria or p.categoria, " ".join(p.colores), p.estampado or "", p.material or "",
              p.marca or "", p.descripcion]
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
    # Todo queda en temporal/ hasta que el usuario confirme (POST /prendas)
    original = fotos.guardar_original(img, carpeta=fotos.TEMPORAL)
    # Recorte (CPU local) y etiquetado (Gemini) en paralelo.
    recorte, etiquetas = await asyncio.gather(
        run_in_threadpool(fotos.recortar_fondo, img, fotos.TEMPORAL),
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
    p.normalizar()
    vector = np.array(embed([_texto_embedding(p)])[0])
    # Confirmada: sus fotos salen de temporal/
    p.foto_original = fotos.confirmar(p.foto_original, "originales")
    p.foto_recortada = fotos.confirmar(p.foto_recortada, "recortes")
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {S}.prendas (foto_original, foto_recortada, categoria, subcategoria, colores, estampado,
                    material, formalidad, temporada, ocasiones, descripcion, talla, marca, ajuste, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector) RETURNING id""",
            (p.foto_original, p.foto_recortada, p.categoria, p.subcategoria, p.colores, p.estampado, p.material,
             p.formalidad, p.temporada, p.ocasiones, p.descripcion, p.talla, p.marca, p.ajuste, vector),
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
    p.normalizar()
    vector = np.array(embed([_texto_embedding(p)])[0])
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {S}.prendas SET categoria=%s, subcategoria=%s, colores=%s, estampado=%s, material=%s,
                    formalidad=%s, temporada=%s, ocasiones=%s, descripcion=%s, talla=%s, marca=%s, ajuste=%s,
                    embedding=%s::vector
                WHERE id=%s AND activa""",
            (p.categoria, p.subcategoria, p.colores, p.estampado, p.material, p.formalidad, p.temporada,
             p.ocasiones, p.descripcion, p.talla, p.marca, p.ajuste, vector, prenda_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Prenda no encontrada")
    return {"ok": True}


class BajaIn(BaseModel):
    motivo: str | None = None
    nota: str = ""


def _dar_de_baja(prenda_id: int, motivo: str | None, nota: str):
    if motivo is not None and motivo not in params.MOTIVOS_BAJA:
        raise HTTPException(400, f"Motivo invalido: {motivo}")
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {S}.prendas SET activa = FALSE, baja_motivo = %s, baja_nota = %s, baja_fecha = CURRENT_DATE
                WHERE id = %s AND activa""",
            (motivo, nota.strip() or None, prenda_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Prenda no encontrada")
    return {"ok": True}


@app.delete("/prendas/{prenda_id}")
def baja_prenda(prenda_id: int):
    """Baja logica sin motivo: la prenda deja de aparecer pero se conserva su historial de usos."""
    return _dar_de_baja(prenda_id, None, "")


@app.post("/prendas/{prenda_id}/baja")
def baja_con_motivo(prenda_id: int, b: BajaIn):
    """Sacar la prenda del closet diciendo por que (regalada, donada, rota...)."""
    return _dar_de_baja(prenda_id, b.motivo, b.nota)


@app.get("/bajas")
def listar_bajas():
    """Lo que ya salio del closet: motivo, fecha y cuanto se uso mientras estuvo."""
    with conexion() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""SELECT p.id, p.foto_original, p.foto_recortada, p.categoria, p.subcategoria, p.colores,
                       p.baja_motivo, p.baja_nota, p.baja_fecha, p.created_at,
                       count(u.id) AS veces_usada, max(u.fecha) AS ultimo_uso
                FROM {S}.prendas p LEFT JOIN {S}.usos u ON u.prenda_id = p.id
                WHERE NOT p.activa
                GROUP BY p.id ORDER BY p.baja_fecha DESC NULLS LAST, p.id DESC"""
        )
        bajas = cur.fetchall()
    resumen: dict[str, int] = {}
    for b in bajas:
        resumen[b["baja_motivo"] or "sin_motivo"] = resumen.get(b["baja_motivo"] or "sin_motivo", 0) + 1
    return {"motivos": params.MOTIVOS_BAJA, "resumen": resumen, "bajas": bajas}


@app.post("/prendas/{prenda_id}/restaurar")
def restaurar_prenda(prenda_id: int):
    """Regresar una prenda al closet (por si fue un error)."""
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {S}.prendas SET activa = TRUE, baja_motivo = NULL, baja_nota = NULL, baja_fecha = NULL
                WHERE id = %s AND NOT activa""",
            (prenda_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Prenda no encontrada")
    return {"ok": True}


def _prendas(where: str = "", args: tuple | list = ()) -> list[dict]:
    with conexion() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT {', '.join(COLUMNAS)} FROM {S}.v_prendas_uso {where}", args)
        return cur.fetchall()


def _prenda_o_404(prenda_id: int) -> dict:
    filas = _prendas("WHERE id = %s", (prenda_id,))
    if not filas:
        raise HTTPException(404, "Prenda no encontrada")
    return filas[0]


# ---------- Cuidado (etiqueta de lavado) ----------

class FibraIn(BaseModel):
    fibra: str
    porcentaje: int | None = Field(default=None, ge=0, le=100)


class CuidadoIn(BaseModel):
    foto_etiqueta: str | None = None
    simbolos: list[str] = []
    composicion: list[FibraIn] = []
    lavado: str | None = None
    temperatura_max: int | None = Field(default=None, ge=0, le=95)
    blanqueador: str | None = None
    secadora: str | None = None
    secado: str | None = None
    planchado: str | None = None
    tintoreria: str | None = None
    notas: str = ""
    origen: Literal["etiqueta", "tela", "manual"] | None = None  # de donde salieron los simbolos
    # La etiqueta interior suele traer marca y talla: si vienen, se guardan en la prenda
    marca: str | None = None
    talla: str | None = None


@app.post("/prendas/{prenda_id}/etiqueta/analizar")
async def analizar_etiqueta(prenda_id: int, foto: UploadFile = File(...)):
    """Guarda la foto de la etiqueta y propone composicion + cuidado. No guarda en la prenda:
    la app muestra la propuesta y luego llama a PUT /prendas/{id}/cuidado."""
    _prenda_o_404(prenda_id)
    try:
        img = fotos.normalizar(await foto.read())
    except Exception:
        raise HTTPException(400, "No pude leer la imagen")
    ruta = fotos.guardar_original(img, carpeta=fotos.TEMPORAL)  # se confirma en PUT /prendas/{id}/cuidado
    try:
        cuidado = await run_in_threadpool(get_provider().leer_etiqueta_cuidado, fotos.a_jpeg_bytes(img), "image/jpeg")
        cuidado = asdict(cuidado)
    except Exception as e:
        print(f"leer_etiqueta_cuidado fallo: {e}")
        cuidado = None
    return {"foto_etiqueta": ruta, "cuidado": cuidado}


@app.put("/prendas/{prenda_id}/cuidado")
def guardar_cuidado(prenda_id: int, c: CuidadoIn):
    _validar_ruta(c.foto_etiqueta)
    _prenda_o_404(prenda_id)
    c.foto_etiqueta = fotos.confirmar(c.foto_etiqueta, "etiquetas")
    datos = c.model_dump(exclude={"foto_etiqueta", "composicion", "marca", "talla"})
    marca = " ".join((c.marca or "").split()) or None
    talla = normalizar_talla(c.talla)
    if c.simbolos:
        # Los simbolos mandan: las instrucciones se recalculan desde el diccionario
        t = simbolos_cuidado.traducir(c.simbolos)
        for campo in ("lavado", "temperatura_max", "blanqueador", "secadora", "secado", "planchado", "tintoreria"):
            datos[campo] = t.get(campo)
        datos["simbolos"] = t["simbolos"]
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {S}.prendas SET composicion = %s, cuidado = %s,
                    foto_etiqueta = COALESCE(%s, foto_etiqueta),
                    marca = COALESCE(%s, marca), talla = COALESCE(%s, talla)
                WHERE id = %s AND activa""",
            (Json([f.model_dump() for f in c.composicion]), Json(datos), c.foto_etiqueta, marca, talla, prenda_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Prenda no encontrada")
    return {"ok": True}


# ---------- Usos ("me lo puse hoy") ----------

class UsoIn(BaseModel):
    prendas: list[int] = Field(min_length=1)
    fecha: date | None = None
    outfit_id: int | None = None


@app.post("/usos")
def registrar_uso(u: UsoIn):
    fecha = u.fecha or date.today()
    with conexion() as conn, conn.cursor() as cur:
        for pid in u.prendas:
            cur.execute(
                f"""INSERT INTO {S}.usos (prenda_id, outfit_id, fecha) VALUES (%s, %s, %s)
                    ON CONFLICT (prenda_id, fecha) DO NOTHING""",
                (pid, u.outfit_id, fecha),
            )
    return {"ok": True, "fecha": fecha}


@app.delete("/usos")
def deshacer_uso(prendas: list[int] = Query(...), fecha: date | None = None):
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(f"DELETE FROM {S}.usos WHERE prenda_id = ANY(%s) AND fecha = %s",
                    (prendas, fecha or date.today()))
    return {"ok": True}


# ---------- Outfits ----------

class OutfitIn(BaseModel):
    prendas: list[int] = Field(min_length=2)
    nombre: str | None = None
    ocasion: str | None = None
    fuente: str = "manual"
    aceptado: bool | None = True
    explicacion: str | None = None


@app.post("/outfits")
def guardar_outfit(o: OutfitIn):
    if o.fuente not in ("ia", "manual"):
        raise HTTPException(400, "fuente debe ser ia o manual")
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {S}.outfits (nombre, ocasion, prendas, fuente, aceptado, explicacion)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (o.nombre, o.ocasion, o.prendas, o.fuente, o.aceptado, o.explicacion),
        )
        return {"id": cur.fetchone()[0]}


@app.get("/outfits")
def listar_outfits(limite: int = 30):
    with conexion() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""SELECT id, nombre, ocasion, prendas, fuente, aceptado, explicacion, imagen_tryon, created_at
                FROM {S}.outfits WHERE aceptado IS NOT FALSE ORDER BY created_at DESC LIMIT %s""",
            (limite,),
        )
        outfits = cur.fetchall()
    ids = {i for o in outfits for i in o["prendas"]}
    por_id = {p["id"]: p for p in _prendas("WHERE id = ANY(%s)", (list(ids),))} if ids else {}
    for o in outfits:
        o["prendas"] = [por_id[i] for i in o["prendas"] if i in por_id]
    return outfits


@app.get("/outfit/armar")
def armar_outfit(base: int, fijas: list[int] = Query(default=[]), extras: list[str] = Query(default=[])):
    """Prenda base + prendas fijadas -> opciones ordenadas para cada slot faltante.
    extras: slots que solo salen si se piden (bolsa/mochila)."""
    closet = _prendas()
    por_id = {p["id"]: p for p in closet}
    if base not in por_id:
        raise HTTPException(404, "Prenda base no encontrada")
    fijadas = [por_id[i] for i in fijas if i in por_id and i != base]
    return combinador.armar(por_id[base], fijadas, closet, extras=extras)


# ---------- Tallas y marcas ----------

@app.get("/tallas")
def tallas_y_marcas():
    """Que tallas y marcas tiene el closet, por categoria. Sirve para comprar y para autocompletar."""
    prendas = _prendas()
    por_cat: dict[str, dict] = {}
    marcas: dict[str, dict] = {}
    for p in prendas:
        c = por_cat.setdefault(p["categoria"], {"categoria": p["categoria"], "prendas": 0, "tallas": {}, "marcas": {}, "ajustes": {}})
        c["prendas"] += 1
        if p["talla"]:
            c["tallas"][p["talla"]] = c["tallas"].get(p["talla"], 0) + 1
        if p["ajuste"]:
            c["ajustes"][p["ajuste"]] = c["ajustes"].get(p["ajuste"], 0) + 1
        if p["marca"]:
            # 'zara' y 'ZARA' son la misma marca: se muestra como se escribio mas veces
            m = marcas.setdefault(p["marca"].lower(), {"grafias": {}, "prendas": 0, "categorias": set()})
            m["grafias"][p["marca"]] = m["grafias"].get(p["marca"], 0) + 1
            m["prendas"] += 1
            m["categorias"].add(p["categoria"])
    nombre = {k: max(m["grafias"], key=m["grafias"].get) for k, m in marcas.items()}
    for p in prendas:
        if p["marca"]:
            c = por_cat[p["categoria"]]
            n = nombre[p["marca"].lower()]
            c["marcas"][n] = c["marcas"].get(n, 0) + 1
    orden = lambda d: [{"valor": k, "prendas": v} for k, v in sorted(d.items(), key=lambda x: (-x[1], x[0]))]
    categorias = [
        {**c, "tallas": orden(c["tallas"]), "marcas": orden(c["marcas"]), "ajustes": orden(c["ajustes"]),
         "sin_talla": c["prendas"] - sum(c["tallas"].values())}
        for c in sorted(por_cat.values(), key=lambda c: params.CATEGORIAS.index(c["categoria"]))
    ]
    lista_marcas = sorted(
        ({"marca": nombre[k], "prendas": m["prendas"], "categorias": sorted(m["categorias"])} for k, m in marcas.items()),
        key=lambda m: (-m["prendas"], m["marca"].lower()),
    )
    return {"total": len(prendas), "con_talla": sum(1 for p in prendas if p["talla"]),
            "categorias": categorias, "marcas": lista_marcas, "ajustes": params.AJUSTES}


# ---------- Olvidadas ----------

@app.get("/prendas/olvidadas")
def olvidadas(dias: int = params.DIAS_OLVIDADA):
    """Dos listas: prendas usadas alguna vez pero no en `dias` dias, y prendas nunca usadas
    (las agregadas hace mas de 7 dias, para no marcar lo que acabas de cargar)."""
    sin_usar = _prendas("WHERE ultimo_uso < CURRENT_DATE - %s ORDER BY ultimo_uso", (dias,))
    nunca = _prendas("WHERE ultimo_uso IS NULL AND created_at < now() - interval '7 days' ORDER BY created_at")
    return {"dias": dias, "sin_usar": sin_usar, "nunca_usadas": nunca}


# ---------- Lavanderia ----------

class LavanderiaIn(BaseModel):
    prendas: list[int] = Field(min_length=1)


@app.post("/lavanderia")
def armar_cargas(l: LavanderiaIn):
    prendas = _prendas("WHERE id = ANY(%s)", (l.prendas,))
    return {"cargas": lavanderia.agrupar(prendas)}


@app.get("/cuidado/simbolos")
def diccionario_simbolos():
    """Diccionario oficial de simbolos (ISO 3758) para mostrarlos en la app."""
    return simbolos_cuidado.describir(simbolos_cuidado.CODIGOS)


@app.get("/cuidado/guia")
def guia_cuidado_completa():
    """Como leer cada grupo de simbolos, cuidado tipico por tela y por articulo de la casa."""
    return guia_cuidado.guia()


class EstimarIn(BaseModel):
    fibras: list[str] = Field(min_length=1)


@app.post("/cuidado/estimar")
def estimar_cuidado(e: EstimarIn):
    """Para prendas sin etiqueta o ilegible: simbolos sugeridos segun la tela."""
    r = guia_cuidado.estimar(e.fibras)
    if not r:
        raise HTTPException(422, "No reconozco esa tela")
    return r
