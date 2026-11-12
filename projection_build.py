"""
projection_build.py -- rebuild lado-nube del graph_aec (camino B).

Port de Ek-Chuah/proyeccion.py::reconstruir de SQLite a Postgres. La logica
de poblado es IDENTICA (INSERT OR IGNORE -> ON CONFLICT DO NOTHING; primera_captura
= min(capture_ts) orden-independiente); por eso el falsador I1 ("borrar y rehacer
del log = identico") se cumple igual y, ademas, el dump logico de este rebuild
Postgres coincide con el de la proyeccion SQLite del substrato sobre el mismo log.

Dos capas (ver schema.sql):
  - aec_log    : copia replicada del log durable. La VERDAD en la nube.
  - proyeccion : tablas regenerables (_TABLAS_PROYECCION, lista canonica).
                 rebuild_projection las trunca y rehace.

El embedding de afirmacion es indice (regenerable), no verdad: se computa aparte
y dump_logico() lo excluye.

EL BORDE (JOINT, SOL a CodeCS): replicate_log_from_file() es el cargador de PRUEBA
LOCAL. En produccion el exportador de CodeCS llena aec_log (mismo line_sha canonico).
Ver docs/ek_chuah/SOL_EXPORTADOR_LOG_AEC_*.md.

Uso CLI:
    python projection_build.py --schema                       # crea schema
    python projection_build.py --replicate ../AEC/log/inscripciones.jsonl
    python projection_build.py --rebuild                      # reconstruye + embeddings
    python projection_build.py --rebuild --no-embeddings
    python projection_build.py --embed-missing                # backfill solo NULL (no trunca)
    python projection_build.py --dump                         # volcado logico (I1)
"""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import os
import sys
import time

from sqlalchemy import text

from db import get_engine
import embeddings
from embeddings import TASK_DOCUMENT

logger = logging.getLogger(__name__)

_TABLAS_PROYECCION = ["inscripcion", "necesidad", "consulta", "referente",
                      "version", "afirmacion", "referente_assert", "revision"]

# Reintentos del embed: un flake transitorio de Gemini NO debe dejar un vector NULL en
# silencio. Incidente 2026-11-12: un rebuild-on-boot embebio 97/98 -- la 98a flakeo y el
# `if not emb: continue` la dejo NULL sin aviso, borrando su vector bueno (el rebuild TRUNCA).
_EMBED_RETRIES = int(os.environ.get("AEC_EMBED_RETRIES", "3"))


def _embed_reintentando(txt: str, intentos: int = _EMBED_RETRIES):
    """embed(TASK_DOCUMENT) con reintento + backoff. None solo si agota los intentos."""
    for i in range(intentos):
        emb = embeddings.embed(txt, TASK_DOCUMENT)
        if emb:
            return emb
        if i + 1 < intentos:
            time.sleep(0.5 * (i + 1))
    return None


def _canon_line(ev: dict) -> str:
    """Serializacion canonica identica a aec_store.append_event (paridad de line_sha)."""
    return json.dumps(ev, ensure_ascii=False, sort_keys=True)


def _line_sha(ev: dict) -> str:
    return hashlib.sha256(_canon_line(ev).encode("utf-8")).hexdigest()


def _j(obj) -> str:
    """Espeja proyeccion._j: JSON canonico para columnas TEXT (paridad dump logico)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


# ════════════════════════════════════════════════════════════════
# schema
# ════════════════════════════════════════════════════════════════

def ensure_schema(engine) -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "schema.sql"), "r", encoding="utf-8") as f:
        ddl = f.read()
    # Ejecutar el script completo de una: psycopg2 parsea multi-statement e ignora
    # correctamente los ';' dentro de comentarios '--' (un split manual por ';' los
    # rompe -> "can't execute an empty query").
    with engine.begin() as cx:
        cx.exec_driver_sql(ddl)
    logger.info("schema asegurado")


# ════════════════════════════════════════════════════════════════
# capa 1: replicacion del log (SEAM JOINT -- en prod lo hace CodeCS)
# ════════════════════════════════════════════════════════════════

def replicate_log_from_file(path: str, engine) -> int:
    """Cargador de PRUEBA LOCAL: vierte un inscripciones.jsonl a aec_log.

    Idempotente: line_sha UNIQUE + ON CONFLICT DO NOTHING. Re-correr = no-op.
    En produccion esta funcion la reemplaza el exportador de CodeCS (SOL),
    que debe usar EXACTAMENTE el mismo line_sha canonico.
    """
    n = 0
    with engine.begin() as cx, open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            res = cx.execute(text(
                "INSERT INTO aec_log (line_sha, event) VALUES (:sha, CAST(:ev AS jsonb)) "
                "ON CONFLICT (line_sha) DO NOTHING"
            ), {"sha": _line_sha(ev), "ev": _canon_line(ev)})
            n += res.rowcount or 0
    logger.info("replicados %d eventos nuevos a aec_log desde %s", n, path)
    return n


def _iter_log(cx):
    rows = cx.execute(text("SELECT event FROM aec_log ORDER BY seq ASC")).fetchall()
    for r in rows:
        ev = r[0]
        yield json.loads(ev) if isinstance(ev, str) else ev


# ════════════════════════════════════════════════════════════════
# capa 2: rebuild de la proyeccion (port de reconstruir)
# ════════════════════════════════════════════════════════════════

def rebuild_projection(engine, with_embeddings: bool = True) -> dict:
    """Trunca _TABLAS_PROYECCION y las reconstruye de aec_log. Idempotente/determinista."""
    with engine.begin() as cx:
        cx.execute(text("TRUNCATE " + ", ".join(_TABLAS_PROYECCION)))
        for ev in _iter_log(cx):
            kind = ev.get("ev")
            ts = ev.get("ts")
            if kind == "inscripcion":
                cx.execute(text(
                    "INSERT INTO inscripcion "
                    "(id,premisa,busqueda,resultados_crudos,conclusion,"
                    "inferidor_model,inferidor_ts,huella,ts) VALUES "
                    "(:id,:premisa,:busqueda,:resultados,:conclusion,:im,:its,:huella,:ts) "
                    "ON CONFLICT (id) DO NOTHING"),
                    {"id": ev["id"], "premisa": ev["premisa"],
                     "busqueda": _j(ev["busqueda"]), "resultados": _j(ev["resultados_crudos"]),
                     "conclusion": ev["conclusion"], "im": ev["inferidor_model"],
                     "its": ev["inferidor_ts"], "huella": ev["huella"], "ts": ts})
            elif kind == "necesidad":
                cx.execute(text(
                    "INSERT INTO necesidad (id,pregunta,gatillo,origen_nodo,ts) "
                    "VALUES (:id,:preg,:gat,:org,:ts) "
                    "ON CONFLICT (id) DO NOTHING"),
                    {"id": ev["id"], "preg": ev["pregunta"], "gat": ev["gatillo"],
                     "org": ev.get("origen_nodo"), "ts": ts})
            elif kind == "consulta":
                cx.execute(text(
                    "INSERT INTO consulta (id,nec_id,formulacion,ts) "
                    "VALUES (:id,:nec,:form,:ts) "
                    "ON CONFLICT (id) DO NOTHING"),
                    {"id": ev["id"], "nec": ev["nec_id"], "form": ev["formulacion"], "ts": ts})
            elif kind == "referencia":
                ref = ev["referente_id"]
                cx.execute(text(
                    "INSERT INTO referente (referente_id,primera_captura) VALUES (:ref,:cap) "
                    "ON CONFLICT (referente_id) DO NOTHING"),
                    {"ref": ref, "cap": ev["capture_ts"]})
                cx.execute(text(
                    "UPDATE referente SET primera_captura=:cap "
                    "WHERE referente_id=:ref AND primera_captura > :cap"),
                    {"ref": ref, "cap": ev["capture_ts"]})
                # Columnas NOMBRADAS, no posicionales: `estatus` llego por ALTER TABLE
                # (G-post) y en la BD ya desplegada quedo AL FINAL, no donde la pone el
                # CREATE TABLE. Un INSERT posicional permutaba estatus<->ts en prod.
                cx.execute(text(
                    "INSERT INTO version "
                    "(id,referente_id,content_hash,url_cruda,capture_ts,fecha_fuente,"
                    "q_id,estatus,ts) VALUES (:id,:ref,:ch,:url,:cap,:ff,:q,:est,:ts) "
                    "ON CONFLICT (id) DO NOTHING"),
                    {"id": ev["id"], "ref": ref, "ch": ev["content_hash"],
                     "url": ev["url_cruda"], "cap": ev["capture_ts"],
                     "ff": ev["fecha_fuente"], "q": ev["q_id"],
                     "est": ev.get("estatus", "viva"), "ts": ts})
            elif kind == "afirmacion":
                cx.execute(text(
                    "INSERT INTO afirmacion (id,txt,insc_id,ref_id,tipo,estatus,ts) "
                    "VALUES (:id,:txt,:insc,:ref,:tipo,:est,:ts) ON CONFLICT (id) DO NOTHING"),
                    {"id": ev["id"], "txt": ev["txt"], "insc": ev["insc_id"],
                     "ref": ev.get("ref_id"), "tipo": ev["tipo"],
                     "est": ev["estatus"], "ts": ts})
            elif kind == "referente_assert":
                cx.execute(text(
                    "INSERT INTO referente_assert "
                    "(id,referente_a,referente_b,relacion,gatillo,ts) "
                    "VALUES (:id,:a,:b,:rel,:gat,:ts)"),
                    {"id": ev["id"], "a": ev["referente_a"], "b": ev["referente_b"],
                     "rel": ev["relacion"], "gat": ev["gatillo"], "ts": ts})
            elif kind == "revision":
                # G-post: reconsideracion append-only. La afirmacion target ya se inserto
                # (la revision llega despues en el log) -> voltear su estatus efectivo. La
                # afirmacion NO se borra (Forma-vs-Valor). Espejo de proyeccion.py (substrato).
                cx.execute(text(
                    "INSERT INTO revision "
                    "(id,target_af,nuevo_estatus,reemplazada_por,motivo,gatillo,ts) "
                    "VALUES (:id,:t,:ne,:rp,:mot,:gat,:ts) "
                    "ON CONFLICT (id) DO NOTHING"),
                    {"id": ev["id"], "t": ev["target_af"], "ne": ev["nuevo_estatus"],
                     "rp": ev.get("reemplazada_por"), "mot": ev.get("motivo"),
                     "gat": ev.get("gatillo"), "ts": ts})
                cx.execute(text("UPDATE afirmacion SET estatus=:ne WHERE id=:t"),
                           {"ne": ev["nuevo_estatus"], "t": ev["target_af"]})

    counts = {}
    with engine.connect() as cx:
        for t in _TABLAS_PROYECCION:
            counts[t] = cx.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()

    embedded = {"embebidas": 0, "fallidas": 0, "fallidas_ids": []}
    if with_embeddings:
        embedded = _build_embeddings(engine)

    logger.info("rebuild ok: %s | embeddings: %s", counts, embedded)
    return {"counts": counts, "embeddings": embedded}


def _build_embeddings(engine) -> dict:
    """Computa embedding de cada afirmacion.txt para aec_search (Gemini, RETRIEVAL_DOCUMENT).

    Regenerable (indice, no verdad): re-correr el rebuild lo recomputa. Reintenta cada embed
    y CUENTA los fallos con log ruidoso (dir. 8/12): un flake no debe dejar un vector NULL en
    silencio -- ese fue el incidente 2026-11-12 (rebuild-on-boot dejo 97/98 sin aviso).
    """
    if not embeddings.available():
        logger.warning("GEMINI_API_KEY ausente: aec_search caera a ILIKE (sin embeddings)")
        return {"embebidas": 0, "fallidas": 0, "fallidas_ids": []}

    with engine.connect() as cx:
        rows = cx.execute(text("SELECT id, txt FROM afirmacion")).fetchall()

    ok, fallidas_ids = 0, []
    with engine.begin() as cx:
        for r in rows:
            emb = _embed_reintentando(r[1])
            if not emb:
                fallidas_ids.append(r[0])
                continue
            vec = "[" + ",".join(str(f) for f in emb) + "]"
            cx.execute(text("UPDATE afirmacion SET embedding = CAST(:v AS vector) WHERE id=:id"),
                       {"v": vec, "id": r[0]})
            ok += 1
    if fallidas_ids:
        logger.warning("rebuild embeddings: %d de %d FALLARON tras reintentos y quedan NULL "
                       "(invisibles al pase semantico): %s", len(fallidas_ids), len(rows),
                       ", ".join(i[:12] for i in fallidas_ids))
    return {"embebidas": ok, "fallidas": len(fallidas_ids), "fallidas_ids": fallidas_ids}


def embed_missing(engine) -> dict:
    """Backfill solo de afirmaciones con embedding NULL. NO trunca la proyeccion (a
    diferencia de --rebuild), asi el lector C3 no ve una ventana de tablas vacias.

    Reporta fallidas EXPLICITAMENTE (dir. 8/12): el modo de falla del 2026-09-16 fue que
    embed() devuelve None en silencio -> el vector quedaba NULL sin aviso. Aqui se cuenta.
    Sigue siendo escritura en produccion: exige autorizacion del Guardian (dir. 5).
    """
    if not embeddings.available():
        logger.warning("GEMINI_API_KEY ausente: no se puede rellenar embeddings (no-op)")
        return {"candidatas": 0, "embebidas": 0, "fallidas": 0}

    with engine.connect() as cx:
        rows = cx.execute(text(
            "SELECT id, txt FROM afirmacion WHERE embedding IS NULL")).fetchall()

    ok, fallidas_ids = 0, []
    with engine.begin() as cx:
        for r in rows:
            emb = _embed_reintentando(r[1])
            if not emb:
                fallidas_ids.append(r[0])
                continue
            vec = "[" + ",".join(str(f) for f in emb) + "]"
            cx.execute(text("UPDATE afirmacion SET embedding = CAST(:v AS vector) WHERE id=:id"),
                       {"v": vec, "id": r[0]})
            ok += 1
    res = {"candidatas": len(rows), "embebidas": ok, "fallidas": len(fallidas_ids),
           "fallidas_ids": fallidas_ids}
    if fallidas_ids:
        logger.warning("embed-missing: %d de %d NO se embebieron tras reintentos -- quedan NULL "
                       "(invisibles al pase semantico): %s", len(fallidas_ids), len(rows),
                       ", ".join(i[:12] for i in fallidas_ids))
    logger.info("embed-missing: %s", res)
    return res


# ════════════════════════════════════════════════════════════════
# falsador I1: dump logico (excluye embedding y la capa aec_log)
# ════════════════════════════════════════════════════════════════

def dump_logico(engine) -> list:
    """Volcado canonico de _TABLAS_PROYECCION para comparar reconstrucciones (I1).

    Excluye afirmacion.embedding (indice regenerable, no verdad). El resultado
    debe coincidir con Ek-Chuah/proyeccion.dump_logico sobre el mismo log.
    """
    cols = {
        "inscripcion": "id,premisa,busqueda,resultados_crudos,conclusion,inferidor_model,inferidor_ts,huella,ts",
        "necesidad": "id,pregunta,gatillo,origen_nodo,ts",
        "consulta": "id,nec_id,formulacion,ts",
        "referente": "referente_id,primera_captura",
        "version": "id,referente_id,content_hash,url_cruda,capture_ts,fecha_fuente,q_id,estatus,ts",
        "afirmacion": "id,txt,insc_id,ref_id,tipo,estatus,ts",
        "referente_assert": "id,referente_a,referente_b,relacion,gatillo,ts",
        "revision": "id,target_af,nuevo_estatus,reemplazada_por,motivo,gatillo,ts",
    }
    out = []
    with engine.connect() as cx:
        for t in _TABLAS_PROYECCION:
            rows = cx.execute(text(f"SELECT {cols[t]} FROM {t}")).fetchall()
            out.append((t, sorted(tuple(r) for r in rows)))
    return out


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="rebuild graph_aec en Postgres (camino B)")
    ap.add_argument("--schema", action="store_true", help="crear/asegurar schema")
    ap.add_argument("--replicate", metavar="JSONL", help="cargar log local a aec_log (prueba)")
    ap.add_argument("--rebuild", action="store_true", help="reconstruir la proyeccion de aec_log")
    ap.add_argument("--no-embeddings", action="store_true", help="rebuild sin embeddings")
    ap.add_argument("--embed-missing", action="store_true",
                    help="backfill solo de embeddings NULL (no trunca; escritura, gateada)")
    ap.add_argument("--dump", action="store_true", help="imprimir dump logico (I1)")
    args = ap.parse_args(argv)

    engine = get_engine()
    if args.schema:
        ensure_schema(engine)
    if args.replicate:
        ensure_schema(engine)
        replicate_log_from_file(args.replicate, engine)
    if args.rebuild:
        res = rebuild_projection(engine, with_embeddings=not args.no_embeddings)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.embed_missing:
        res = embed_missing(engine)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.dump:
        for t, rows in dump_logico(engine):
            print(f"# {t}: {len(rows)} filas")
            for row in rows:
                print(json.dumps(row, ensure_ascii=False, default=str))

    if not any([args.schema, args.replicate, args.rebuild, args.embed_missing, args.dump]):
        ap.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
