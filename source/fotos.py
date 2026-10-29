"""Guardado de fotos: redimensiona, corrige orientacion y recorta el fondo con rembg."""

import io
import os
import threading
import time
import uuid

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

import params

register_heif_opener()
_sesion_rembg = None
_lock_rembg = threading.Lock()


def _rembg():
    global _sesion_rembg
    with _lock_rembg:  # evita cargar el modelo dos veces si llega una foto durante la precarga
        if _sesion_rembg is None:
            from rembg import new_session
            _sesion_rembg = new_session(params.REMBG_MODEL)
    return _sesion_rembg


def normalizar(datos: bytes) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(datos))).convert("RGB")
    img.thumbnail((params.MAX_LADO_FOTO, params.MAX_LADO_FOTO))
    return img


def guardar_original(img: Image.Image, carpeta: str = "originales") -> str:
    ruta = f"{carpeta}/{uuid.uuid4().hex}.jpg"
    img.save(os.path.join(params.MEDIA_DIR, ruta), "JPEG", quality=88)
    return ruta


def recortar_fondo(img: Image.Image, carpeta: str = "recortes") -> str:
    from rembg import remove
    sin_fondo = remove(img, session=_rembg())
    bbox = sin_fondo.getbbox()
    if bbox:
        sin_fondo = sin_fondo.crop(bbox)
    ruta = f"{carpeta}/{uuid.uuid4().hex}.png"
    sin_fondo.save(os.path.join(params.MEDIA_DIR, ruta), "PNG", optimize=True)
    return ruta


def a_jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


# ---------- Fotos temporales ----------
# Lo que se analiza sin confirmar (prenda nueva, etiqueta, modo tienda) vive en media/temporal/.
# Al confirmar se mueve a su carpeta final; si se descarta o se abandona, se borra.
TEMPORAL = "temporal"
CARPETAS_PRENDAS = ("originales", "recortes", "etiquetas")


def _ruta_abs(ruta: str) -> str:
    return os.path.join(params.MEDIA_DIR, ruta)


def es_temporal(ruta: str | None) -> bool:
    return bool(ruta) and ruta.startswith(f"{TEMPORAL}/") and "/" not in ruta[len(TEMPORAL) + 1:] and ".." not in ruta


def confirmar(ruta: str | None, destino: str) -> str | None:
    """Mueve una foto temporal a su carpeta definitiva y devuelve la ruta nueva.
    Si la ruta ya es definitiva, la deja igual."""
    if not es_temporal(ruta):
        return ruta
    nueva = f"{destino}/{os.path.basename(ruta)}"
    os.replace(_ruta_abs(ruta), _ruta_abs(nueva))
    return nueva


def descartar(rutas: list[str]) -> int:
    """Borra fotos temporales (solo de media/temporal/). Devuelve cuantas borro."""
    borradas = 0
    for r in rutas:
        if es_temporal(r) and os.path.isfile(_ruta_abs(r)):
            os.remove(_ruta_abs(r))
            borradas += 1
    return borradas


def limpiar(rutas_en_uso: set[str] | None, horas: float) -> dict:
    """Borra temporales con mas de `horas`. Si se pasan las rutas en uso, tambien borra fotos
    de prendas (originales/recortes/etiquetas) que ninguna prenda usa y tienen mas de `horas`."""
    limite = time.time() - horas * 3600
    resultado = {"temporales": 0, "huerfanas": 0}
    carpetas = [(TEMPORAL, "temporales")]
    if rutas_en_uso is not None:
        carpetas += [(c, "huerfanas") for c in CARPETAS_PRENDAS]
    for carpeta, clave in carpetas:
        d = _ruta_abs(carpeta)
        if not os.path.isdir(d):
            continue
        for nombre in os.listdir(d):
            ruta = f"{carpeta}/{nombre}"
            completo = os.path.join(d, nombre)
            if not os.path.isfile(completo) or os.path.getmtime(completo) > limite:
                continue
            if clave == "huerfanas" and ruta in rutas_en_uso:
                continue
            os.remove(completo)
            resultado[clave] += 1
    return resultado
