import os

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import params
from source import simbolos_cuidado
from source.ia.base import CuidadoPrenda, EtiquetasPrenda, Fibra, IAProvider, PropuestaOutfit

PROMPT_ETIQUETAR = f"""Eres un estilista. Analiza la prenda principal de la foto y responde en español.
- categoria: una de {params.CATEGORIAS} (top = camisa, playera, sudadera, suéter; bottom = pantalón, short, falda;
  chamarra = chamarra, saco, abrigo, chaleco; accesorio = cinturón, reloj, gorra, lentes, corbata, bufanda;
  bolsa = mochila, bolsa, maletín, cangurera, tote).
- subcategoria: tipo concreto (ej. "camisa oxford", "jeans slim", "tenis blancos").
- colores: colores dominantes, el principal primero, nombres simples en español.
- estampado: liso, rayas, cuadros, estampado, etc.
- material: estimado (algodón, mezclilla, piel, lana...).
- formalidad: 1 (muy casual) a 5 (muy formal).
- temporada: de ["calor", "templado", "frio"], las que apliquen.
- ocasiones: de ["casa", "casual", "oficina", "salir", "formal", "deporte"], las que apliquen.
- marca: solo si se ve claramente un logo o una etiqueta con la marca; si no, cadena vacía. No adivines.
- descripcion: 1-2 frases que describan la prenda (color, corte, estilo) para poder buscarla luego por similitud."""


PROMPT_CUIDADO = f"""Lee la etiqueta de cuidado de esta prenda.
1. simbolos: identifica los símbolos internacionales de cuidado (ISO 3758) que aparecen y devuelve SOLO
   códigos de esta lista, uno por símbolo visible: {", ".join(simbolos_cuidado.CODIGOS)}.
   Guía: tina = lavado (los puntos o el número dan la temperatura: 1 punto=30, 2=40, 3=50, 4=60; rayas debajo = suave),
   mano en la tina = lavado_mano; triángulo = blanqueador; cuadro con círculo = secadora (puntos = temperatura,
   círculo relleno = sin calor); cuadro con líneas = secado natural; plancha = planchado (puntos = temperatura);
   círculo con letra = tintorería. Un símbolo tachado con X es la versión "no_".
   Si el texto contradice un símbolo, manda el símbolo. No incluyas códigos de símbolos que no veas.
2. composicion: cada fibra con su porcentaje, en minúsculas y en español (algodón, poliéster, elastano, lana,
   viscosa, lino, nailon, seda...). Si hay varias partes (forro, exterior), usa la tela exterior.
3. notas: advertencias escritas en la etiqueta ("lavar con colores similares", "lavar al revés"), en español.
   Vacío si no hay.
4. marca y talla: si aparecen en la foto, tal cual (ej. "ZARA", "M", "MX 27"). Vacío si no se ven;
   no adivines la talla por el tamaño de la prenda. Camisa con talla de cuello y manga: "cuello/manga"
   (ej. "15.5/32-33" o "39/84"). Pantalón con cintura y largo: "cintura/largo" (ej. "32/30")."""


class _FibraSchema(BaseModel):
    fibra: str
    porcentaje: int | None = None


class _CuidadoSchema(BaseModel):
    simbolos: list[str]
    composicion: list[_FibraSchema]
    notas: str = ""
    marca: str = ""
    talla: str = ""


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
    marca: str = ""


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
        return EtiquetasPrenda(**{**datos.model_dump(), "categoria": cat, "marca": datos.marca.strip() or None})

    def leer_etiqueta_cuidado(self, foto: bytes, mime: str) -> CuidadoPrenda:
        resp = self.cliente.models.generate_content(
            model=self.modelo_texto,
            contents=[types.Part.from_bytes(data=foto, mime_type=mime), PROMPT_CUIDADO],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_CuidadoSchema,
                temperature=0.1,
            ),
        )
        datos: _CuidadoSchema = resp.parsed
        t = simbolos_cuidado.traducir(datos.simbolos)
        notas = "; ".join(x for x in [datos.notas, *t["notas_simbolos"]] if x)
        return CuidadoPrenda(
            composicion=[Fibra(**f.model_dump()) for f in datos.composicion],
            simbolos=t["simbolos"],
            lavado=t.get("lavado"),
            temperatura_max=t.get("temperatura_max"),
            blanqueador=t.get("blanqueador"),
            secadora=t.get("secadora"),
            secado=t.get("secado"),
            planchado=t.get("planchado"),
            tintoreria=t.get("tintoreria"),
            notas=notas,
            marca=datos.marca.strip() or None,
            talla=datos.talla.strip() or None,
        )

    # Fase 2 (outfits con IA) y Fase 3 (try-on).
    def proponer_outfits(self, pedido: str, candidatos: list[dict], n: int = 3) -> list[PropuestaOutfit]:
        raise NotImplementedError

    def generar_tryon(self, foto_usuario: bytes, fotos_prendas: list[bytes]) -> bytes:
        raise NotImplementedError
