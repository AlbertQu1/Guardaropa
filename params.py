import os

# Se puede sobreescribir para pruebas (ej. GUARDARROPA_SCHEMA=guardarropa_test)
DB_SCHEMA = os.environ.get("GUARDARROPA_SCHEMA", "guardarropa")

EMBEDDINGS_SERVICE_URL = "http://127.0.0.1:8001"
EMBEDDING_DIM = 384

MEDIA_DIR = "media"
REMBG_MODEL = "u2netp"  # modelo ligero, CPU
MAX_LADO_FOTO = 1600  # px, se redimensiona al subir
HORAS_FOTO_TEMPORAL = 24  # foto analizada sin confirmar: se borra despues de esto
HORAS_ENTRE_LIMPIEZAS = 6

GEMINI_MODELO_TEXTO = "gemini-flash-latest"

CATEGORIAS = ["top", "bottom", "calzado", "chamarra", "accesorio", "bolsa", "vestido_completo"]
AJUSTES = ["ajustado", "regular", "holgado", "oversize"]  # como le queda la prenda
# Motivos para sacar una prenda del closet (baja logica, se conserva el historial)
MOTIVOS_BAJA = {
    "regalada": "Regalada", "donada": "Donada", "vendida": "Vendida", "rota": "Rota o desgastada",
    "no_queda": "Ya no me queda", "no_gusta": "Ya no me gusta", "perdida": "Se perdió", "otro": "Otro",
}
DIAS_OLVIDADA = 60  # prenda sin usar en estos dias aparece en "Olvidadas"

# Combinador "Arma tu outfit"
OPCIONES_POR_SLOT = 6
# Colores que combinan con todo
COLORES_NEUTROS = {
    "negro", "blanco", "gris", "gris oscuro", "gris claro", "beige", "crema", "arena", "camel",
    "café", "cafe", "marrón", "caqui", "khaki", "azul marino", "marino", "mezclilla", "denim", "hueso",
}
