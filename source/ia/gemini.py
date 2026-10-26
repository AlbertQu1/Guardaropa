import os

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import params
from source.ia.base import EtiquetasPrenda, IAProvider, PropuestaOutfit

PROMPT_ETIQUETAR = f"""Eres un estilista. Analiza la prenda principal de la foto y responde en español.
- categoria: una de {params.CATEGORIAS} (top = camisa, playera, sudadera, suéter; bottom = pantalón, short, falda;
  chamarra = chamarra, saco, abrigo, chaleco; accesorio = cinturón, reloj, gorra, lentes, bolsa, corbata, bufanda).
- subcategoria: tipo concreto (ej. "camisa oxford", "jeans slim", "tenis blancos").
- colores: colores dominantes, el principal primero, nombres simples en español.
- estampado: liso, rayas, cuadros, estampado, etc.
- material: estimado (algodón, mezclilla, piel, lana...).
- formalidad: 1 (muy casual) a 5 (muy formal).
- temporada: de ["calor", "templado", "frio"], las que apliquen.
- ocasiones: de ["casa", "casual", "oficina", "salir", "formal", "deporte"], las que apliquen.
- descripcion: 1-2 frases que describan la prenda (color, corte, estilo) para poder buscarla luego por similitud."""


class _EtiquetasSchema(BaseModel):
    categoria: str
    subcategoria: str
    colores: list[str]
    estampado: str
    material: str
    formalidad: int = Field(ge=1, le=5)
    temporada: list[str]
    ocasiones: list[str]
    descripcion: str


class GeminiProvider(IAProvider):
    def __init__(self):
        self.cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.modelo_texto = params.GEMINI_MODELO_TEXTO

    def etiquetar_prenda(self, foto: bytes, mime: str) -> EtiquetasPrenda:
        resp = self.cliente.models.generate_content(
            model=self.modelo_texto,
            contents=[types.Part.from_bytes(data=foto, mime_type=mime), PROMPT_ETIQUETAR],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_EtiquetasSchema,
                temperature=0.2,
            ),
        )
        datos: _EtiquetasSchema = resp.parsed
        cat = datos.categoria if datos.categoria in params.CATEGORIAS else "top"
        return EtiquetasPrenda(**{**datos.model_dump(), "categoria": cat})

    # Fase 2 (outfits) y Fase 3 (try-on).
    def proponer_outfits(self, pedido: str, candidatos: list[dict], n: int = 3) -> list[PropuestaOutfit]:
        raise NotImplementedError

    def generar_tryon(self, foto_usuario: bytes, fotos_prendas: list[bytes]) -> bytes:
        raise NotImplementedError
