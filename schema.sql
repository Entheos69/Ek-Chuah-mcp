-- Ek-Chuah MCP (MCP-AEC) -- schema Postgres del graph_aec en la nube
--
-- Camino B (Guardian 2026-06-27): la nube NO recibe la proyeccion ya construida;
-- recibe el LOG (forma Q) y reconstruye la proyeccion aqui. Por eso hay dos capas:
--
--   aec_log         = copia replicada del log durable local (inscripciones.jsonl).
--                     Es la VERDAD en la nube. Append-only. La llena el exportador
--                     de CodeCS (SOL del borde). Lleva content_hash, NUNCA bytes.
--
--   7 tablas        = la proyeccion REGENERABLE. Se truncan y reconstruyen de
--                     aec_log (projection_build.rebuild_projection). Falsador I1:
--                     borrar y rehacer del log = identico.
--
-- afirmacion.embedding = indice pgvector para aec_search. Derivado/regenerable,
--                     no es parte de la verdad del log; el falsador logico I1 lo
--                     excluye (compara solo las columnas que vienen del log).
--
-- Nombres de las 7 tablas IDENTICOS a Ek-Chuah/proyeccion.py (paridad de rebuild
-- SQLite<->Postgres). Esta BD es store nuevo dedicado al dominio AEC -- sin colision.

CREATE EXTENSION IF NOT EXISTS vector;

-- ---- capa 1: el log replicado (la verdad en la nube) ----
CREATE TABLE IF NOT EXISTS aec_log (
    seq         BIGSERIAL PRIMARY KEY,
    line_sha    TEXT UNIQUE NOT NULL,   -- sha256 de la linea JSONL canonica -> replica idempotente
    event       JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- capa 2: la proyeccion regenerable (las 7 tablas, espejo de proyeccion.py) ----
CREATE TABLE IF NOT EXISTS inscripcion (
    id TEXT PRIMARY KEY, premisa TEXT, busqueda TEXT, resultados_crudos TEXT,
    conclusion TEXT, inferidor_model TEXT, inferidor_ts TEXT, huella TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS necesidad (
    id TEXT PRIMARY KEY, pregunta TEXT, gatillo TEXT, origen_nodo TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS consulta (
    id TEXT PRIMARY KEY, nec_id TEXT, formulacion TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS referente (
    referente_id TEXT PRIMARY KEY, primera_captura TEXT
);
CREATE TABLE IF NOT EXISTS version (
    id TEXT PRIMARY KEY, referente_id TEXT, content_hash TEXT, url_cruda TEXT,
    capture_ts TEXT, fecha_fuente TEXT, q_id TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS afirmacion (
    id TEXT PRIMARY KEY, txt TEXT, insc_id TEXT, ref_id TEXT,
    tipo TEXT, estatus TEXT, ts TEXT,
    embedding vector(1536)   -- indice aec_search (Gemini Embedding 001 @1536 via MRL);
                             -- regenerable, fuera del falsador I1
);
CREATE TABLE IF NOT EXISTS referente_assert (
    id TEXT, referente_a TEXT, referente_b TEXT, relacion TEXT, gatillo TEXT, ts TEXT
);

CREATE INDEX IF NOT EXISTS ix_ver_ref ON version(referente_id);
CREATE INDEX IF NOT EXISTS ix_ins_huella ON inscripcion(huella);
CREATE INDEX IF NOT EXISTS ix_af_ref ON afirmacion(ref_id);
CREATE INDEX IF NOT EXISTS ix_af_insc ON afirmacion(insc_id);
CREATE INDEX IF NOT EXISTS ix_consulta_nec ON consulta(nec_id);
