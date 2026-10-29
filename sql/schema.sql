-- Guardarropa: schema en la db casa. Idempotente.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS guardarropa;

CREATE TABLE IF NOT EXISTS guardarropa.prendas (
    id              SERIAL PRIMARY KEY,
    foto_original   TEXT NOT NULL,
    foto_recortada  TEXT,
    categoria       TEXT NOT NULL,
    subcategoria    TEXT,
    colores         TEXT[] NOT NULL DEFAULT '{}',
    estampado       TEXT,
    material        TEXT,
    formalidad      SMALLINT CHECK (formalidad BETWEEN 1 AND 5),
    temporada       TEXT[] NOT NULL DEFAULT '{}',
    ocasiones       TEXT[] NOT NULL DEFAULT '{}',
    descripcion     TEXT,
    embedding       vector(384),
    activa          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS prendas_embedding_hnsw
    ON guardarropa.prendas USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS prendas_categoria_idx ON guardarropa.prendas (categoria) WHERE activa;

CREATE TABLE IF NOT EXISTS guardarropa.outfits (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT,
    ocasion       TEXT,
    prendas       INT[] NOT NULL,
    fuente        TEXT NOT NULL CHECK (fuente IN ('ia', 'manual')),
    aceptado      BOOLEAN,
    explicacion   TEXT,
    imagen_tryon  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS guardarropa.usos (
    id         SERIAL PRIMARY KEY,
    prenda_id  INT NOT NULL REFERENCES guardarropa.prendas(id) ON DELETE CASCADE,
    outfit_id  INT REFERENCES guardarropa.outfits(id) ON DELETE SET NULL,
    fecha      DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (prenda_id, fecha)
);

CREATE TABLE IF NOT EXISTS guardarropa.fotos_usuario (
    id          SERIAL PRIMARY KEY,
    ruta        TEXT NOT NULL,
    principal   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Cuidado de la prenda (2026-10-28): foto de la etiqueta interior, composicion y lavado
ALTER TABLE guardarropa.prendas ADD COLUMN IF NOT EXISTS foto_etiqueta TEXT;
-- [{"fibra": "algodon", "porcentaje": 60}, ...]
ALTER TABLE guardarropa.prendas ADD COLUMN IF NOT EXISTS composicion JSONB;
-- {"lavado": "maquina|mano|no_lavar", "temperatura_max": 30, "blanqueador": "si|no|sin_cloro",
--  "secadora": "no|baja|media|alta", "secado": "tendido|plano|sombra|...", "planchado": "no|baja|media|alta",
--  "tintoreria": "no|si|solo", "notas": "..."}
ALTER TABLE guardarropa.prendas ADD COLUMN IF NOT EXISTS cuidado JSONB;

-- Salida del closet: por que y cuando (regalada, donada, vendida, rota...)
ALTER TABLE guardarropa.prendas ADD COLUMN IF NOT EXISTS baja_motivo TEXT;
ALTER TABLE guardarropa.prendas ADD COLUMN IF NOT EXISTS baja_nota TEXT;
ALTER TABLE guardarropa.prendas ADD COLUMN IF NOT EXISTS baja_fecha DATE;

-- Ultimo uso por prenda: base de la rotacion y de "Olvidadas".
-- Se recrea siempre porque p.* se congela al crear la vista.
DROP VIEW IF EXISTS guardarropa.v_prendas_uso;
CREATE VIEW guardarropa.v_prendas_uso AS
SELECT p.*, u.ultimo_uso, COALESCE(u.veces, 0) AS veces_usada
FROM guardarropa.prendas p
LEFT JOIN (
    SELECT prenda_id, max(fecha) AS ultimo_uso, count(*) AS veces
    FROM guardarropa.usos GROUP BY prenda_id
) u ON u.prenda_id = p.id
WHERE p.activa;
