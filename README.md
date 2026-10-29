# Stylo (backend)

Backend de **Stylo**, un estilista personal inspirado en el clóset digital de *Clueless*:
fotografías tu ropa, la IA la recorta y la etiqueta, y a partir de ahí te ayuda a armar
outfits con lo que ya tienes, a rotar prendas que llevas tiempo sin usar y a decidir si
algo que viste en una tienda combina con tu clóset.

Consumido por la app [Stylo](https://github.com/AlbertQu1/Loggers/tree/master/Guardarropa)
(Next.js PWA, mismo monorepo que Coffee Logger / Boardgames Assistant). Corre en un homelab
(Mac mini 2014 con Ubuntu Server, 8 GB de RAM, sin GPU), así que el diseño cuida mucho
qué se procesa local y qué se manda a la nube.

## Estado actual

- ✅ **Fase 0 — infraestructura**: schema `guardarropa` en Postgres, API FastAPI, servicios
  systemd y HTTPS vía Tailscale.
- ✅ **Fase 1 — clóset digital**: agregar prendas desde el celular (foto → recorte de fondo →
  etiquetado con IA → confirmación manual), galería por categoría, edición y baja.
- ✅ **Cuidado de prendas**: foto de la etiqueta interior → composición de la tela y
  símbolos de lavado. La IA solo identifica qué símbolos aparecen, usando un diccionario
  cerrado de 35 símbolos ISO 3758 (`source/simbolos_cuidado.py`); la traducción a
  instrucciones es determinista. Si corriges un símbolo a mano, las instrucciones se recalculan.
  Si la prenda no tiene etiqueta o la IA no la lee, eliges la tela y se usa el cuidado típico de
  esa tela (en mezclas gana el más delicado), marcado como estimado.
- ✅ **Guía de cuidado**: cómo leer cada grupo de símbolos, cuidado típico de 15 telas y de cosas
  de la casa (sábanas, toallas, cortinas, edredón…) en `source/guia_cuidado.py`.
- ✅ **Lavandería**: eliges lo que vas a lavar y lo separa en cargas compatibles (blancos y
  claros / oscuros / colores, ciclo delicado por fibra, a mano, tintorería), con la temperatura
  máxima de cada carga y avisos por prenda (sin blanqueador, no a la secadora…). Las prendas sin
  etiqueta pero con tela registrada usan el cuidado típico de su tela. Sin IA.
- ✅ **Fase 2a — Arma tu outfit**: eliges una prenda base y el combinador (`source/combinador.py`,
  sin IA) ordena opciones para cada espacio por formalidad, color (neutros combinan con todo,
  máximo un color fuerte), ocasión común, clima, estampados y rotación (lo que no usas sube, pero
  solo como desempate). Fijar una prenda recalcula el resto. "Me lo puse hoy" registra el uso.
- ✅ **Olvidadas**: prendas sin usar en 60+ días y prendas que aún no estrenas.
- ✅ **Bolsas y mochilas**: categoría propia que el combinador no sugiere sola; solo aparece si la
  pides (`extras=bolsa`) o si fijas una.
- ✅ **Tallas y marcas**: cada prenda guarda talla, marca y cómo queda (ajustado, regular, holgado,
  oversize). Camisas por cuello y manga (`15.5/32-33`) y pantalones por cintura y largo (`32/30`).
  La IA las lee de la etiqueta interior. `GET /tallas` resume qué tallas y marcas tienes por categoría.
- ✅ **Salidas**: sacar una prenda del clóset con motivo (regalada, donada, vendida, rota, ya no
  queda…), nota y fecha. Se conserva su historial de uso y se puede regresar al clóset.
- ⏳ **Fase 2b**: "pídeme un outfit" en lenguaje natural ("algo para la oficina, hace frío") y
  modo tienda.
- ⏳ **Fase 3 — try-on y grafo**: ver el outfit puesto en una foto tuya (generación de imagen)
  y un grafo de combinaciones que aprende de los outfits que aceptas o rechazas.

## Cómo funciona

### Agregar una prenda
```
foto (cel) ──► normaliza (orientación EXIF, máx 1600 px, HEIC → JPEG)
           ├─► rembg (u2netp, CPU local) ──► recorte PNG sin fondo
           └─► Gemini (visión) ──► categoría, colores, formalidad, clima, ocasiones, descripción
                                    │
          confirmación en la app ◄──┘
                     │
                     ▼
     embedding de la descripción (embeddingsservice compartido) ──► pgvector
```
El recorte y el etiquetado corren **en paralelo** (~8 s por foto en vez de ~16 s). Nada se
guarda sin que el usuario confirme las etiquetas: la IA propone, tú decides.

### Fotos sin confirmar
Lo que se analiza (prenda nueva, etiqueta de cuidado, y después el modo tienda) se guarda en
`media/temporal/`. Al confirmar se mueve a su carpeta final (`originales/`, `recortes/`,
`etiquetas/`). Si el usuario descarta, la app pide borrarlo en ese momento; si cierra la app sin
confirmar, la API borra cada 6 horas lo temporal con más de 24 horas, y también las fotos que ya no
usa ninguna prenda (las de prendas que salieron del clóset se conservan).

### Por qué vectores *y* grafo
- **pgvector** responde "¿ya tengo algo parecido?": en el modo tienda, una prenda nueva se
  compara contra todo el clóset por similitud de su descripción.
- **Apache AGE** (grafo sobre la misma Postgres) responde "¿con qué combina esto según lo que
  me ha gustado?": relaciones `COMBINA_CON` entre prendas que se refuerzan o debilitan con cada
  outfit aceptado o rechazado. *(Fase 3)*

### IA intercambiable
Toda llamada a IA pasa por una sola interfaz (`source/ia/base.py`): `etiquetar_prenda`,
`leer_etiqueta_cuidado`, `proponer_outfits` y `generar_tryon`. Hoy la implementa `GeminiProvider`. Cambiar a un modelo
local (por ejemplo Ollama con un modelo de visión y ComfyUI para el try-on, en otra máquina
con GPU) es agregar otro provider y cambiar `IA_PROVIDER` en `.env`, sin tocar la API ni la app.

### Decisiones por limitaciones de hardware
- **Sin modelo de embeddings propio**: se reutiliza el `embeddingsservice` que ya corre en el
  servidor (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dim) en vez de cargar CLIP, para no
  gastar ~600 MB extra de RAM.
- **rembg con `u2netp`**: la variante ligera del modelo de recorte. Cargarlo tarda ~50 s en
  este CPU, así que se precarga en segundo plano al arrancar la API.
- **Generación de imágenes en la nube**: el try-on no es viable localmente sin GPU.

## Estructura

```
params.py               constantes (categorías, modelos, rutas)
sql/schema.sql          schema guardarropa (idempotente)
source/api.py           API FastAPI
source/fotos.py         normalización y recorte de fondo
source/combinador.py    "Arma tu outfit" (reglas, sin IA)
source/lavanderia.py    agrupación en cargas de lavado (reglas, sin IA)
source/simbolos_cuidado.py  diccionario ISO 3758 de símbolos de cuidado
source/guia_cuidado.py  guía por tela y por artículo de la casa + estimación sin etiqueta
source/db.py            conexión Postgres + pgvector
source/embeddings_client.py
source/ia/              capa de IA intercambiable (base.py, gemini.py)
media/                  fotos (no versionado)
```

## Modelo de datos (`guardarropa.*`)

| Tabla | Para qué |
|---|---|
| `prendas` | cada prenda: fotos, categoría, colores, formalidad (1-5), clima, ocasiones, descripción, embedding (HNSW coseno), foto de la etiqueta, composición y cuidado (JSONB), talla, marca, ajuste, y motivo/nota/fecha de salida del clóset |
| `outfits` | outfits guardados o propuestos, si se aceptaron y su imagen de try-on |
| `usos` | "me lo puse hoy", base de la rotación |
| `fotos_usuario` | fotos de cuerpo completo para el try-on |
| `v_prendas_uso` | vista con última fecha de uso y veces usada por prenda |

## API

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | estado y conteo de prendas |
| POST | `/prendas/analizar` | sube una foto, devuelve recorte + etiquetas propuestas (no guarda) |
| POST | `/prendas` | guarda una prenda confirmada (mueve sus fotos fuera de `temporal/`) |
| POST | `/temporal/descartar` | borra fotos temporales que el usuario descartó |
| GET | `/prendas?categoria=` | lista el clóset con datos de uso |
| PUT | `/prendas/{id}` | edita etiquetas (recalcula el embedding) |
| DELETE | `/prendas/{id}` | baja lógica sin motivo (conserva el historial de uso) |
| POST | `/prendas/{id}/baja` | sacar del clóset con motivo y nota |
| GET | `/bajas` | lo que salió del clóset: motivo, fecha, veces usada, resumen por motivo |
| POST | `/prendas/{id}/restaurar` | regresar una prenda al clóset |
| POST | `/prendas/{id}/etiqueta/analizar` | foto de la etiqueta → composición + símbolos propuestos (no guarda) |
| PUT | `/prendas/{id}/cuidado` | guarda composición y símbolos (las instrucciones se derivan de los símbolos) |
| GET | `/cuidado/simbolos` | diccionario de símbolos ISO 3758 |
| GET | `/cuidado/guia` | cómo leer los símbolos, cuidado por tela y por artículo de la casa |
| POST | `/cuidado/estimar` | símbolos sugeridos para una prenda sin etiqueta, según sus fibras |
| GET | `/outfit/armar?base=&fijas=&extras=` | opciones ordenadas por espacio para completar el outfit (`extras=bolsa` para pedir bolsa o mochila) |
| POST | `/usos` · DELETE `/usos` | "me lo puse hoy" (idempotente por día) y deshacer |
| POST · GET | `/outfits` | guardar y listar outfits |
| GET | `/tallas` | tallas, marcas y ajustes por categoría (marcas agrupadas sin importar mayúsculas) |
| GET | `/prendas/olvidadas` | sin usar en N días + nunca usadas |
| POST | `/lavanderia` | agrupa prendas en cargas de lavado |

## Setup

```bash
conda env create -f environment.yml
conda activate guardarropa
cp .env.example .env          # DATABASE_URL, GEMINI_API_KEY, IA_PROVIDER
psql casa -f sql/schema.sql   # requiere las extensiones vector y age
uvicorn source.api:app --host 127.0.0.1 --port 8003 --reload
```

Requiere el `embeddingsservice` corriendo en `127.0.0.1:8001`.

## Stack

Python 3.13 · FastAPI · PostgreSQL + pgvector + Apache AGE · rembg · Google Gemini
