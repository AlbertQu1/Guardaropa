"""Guardado de fotos: redimensiona, corrige orientacion y recorta el fondo con rembg."""

import io
import os
import threading
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


def recortar_fondo(img: Image.Image) -> str:
    from rembg import remove
    sin_fondo = remove(img, session=_rembg())
    bbox = sin_fondo.getbbox()
    if bbox:
        sin_fondo = sin_fondo.crop(bbox)
    ruta = f"recortes/{uuid.uuid4().hex}.png"
    sin_fondo.save(os.path.join(params.MEDIA_DIR, ruta), "PNG", optimize=True)
    return ruta


def a_jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()
