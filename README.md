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
- ⏳ **Fase 2 — estilista**: "arma tu outfit" (eliges una prenda base y la app propone el
  resto), "pídeme un outfit" en lenguaje natural ("algo para la oficina, hace frío"),
  registro de uso, rotación de prendas olvidadas y modo tienda.
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

### Por qué vectores *y* grafo
- **pgvector** responde "¿ya tengo algo parecido?": en el modo tienda, una prenda nueva se
  compara contra todo el clóset por similitud de su descripción.
- **Apache AGE** (grafo sobre la misma Postgres) responde "¿con qué combina esto según lo que
  me ha gustado?": relaciones `COMBINA_CON` entre prendas que se refuerzan o debilitan con cada
  outfit aceptado o rechazado. *(Fase 3)*

### IA intercambiable
Toda llamada a IA pasa por una sola interfaz (`source/ia/base.py`): `etiquetar_prenda`,
`proponer_outfits` y `generar_tryon`. Hoy la implementa `GeminiProvider`. Cambiar a un modelo
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
source/db.py            conexión Postgres + pgvector
source/embeddings_client.py
source/ia/              capa de IA intercambiable (base.py, gemini.py)
media/                  fotos (no versionado)
```

## Modelo de datos (`guardarropa.*`)

| Tabla | Para qué |
|---|---|
| `prendas` | cada prenda: fotos, categoría, colores, formalidad (1-5), clima, ocasiones, descripción y su embedding (HNSW coseno) |
| `outfits` | outfits guardados o propuestos, si se aceptaron y su imagen de try-on |
| `usos` | "me lo puse hoy", base de la rotación |
| `fotos_usuario` | fotos de cuerpo completo para el try-on |
| `v_prendas_uso` | vista con última fecha de uso y veces usada por prenda |

## API

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | estado y conteo de prendas |
| POST | `/prendas/analizar` | sube una foto, devuelve recorte + etiquetas propuestas (no guarda) |
| POST | `/prendas` | guarda una prenda confirmada |
| GET | `/prendas?categoria=` | lista el clóset con datos de uso |
| PUT | `/prendas/{id}` | edita etiquetas (recalcula el embedding) |
| DELETE | `/prendas/{id}` | baja lógica (conserva el historial de uso) |

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
