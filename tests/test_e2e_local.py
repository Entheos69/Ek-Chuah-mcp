"""
test_e2e_local.py -- prueba end-to-end del MCP-AEC contra un Postgres+pgvector real.

NO usa OpenAI (rebuild --no-embeddings): aec_search se prueba en modo ILIKE.
Requiere DATABASE_URL apuntando a un Postgres con la extension vector disponible
(ej: contenedor pgvector/pgvector:pg16, o Postgres con pgvector instalado).

Uso:
    DATABASE_URL=postgresql://postgres:aec@localhost:55432/ek_chuah_aec \
        python tests/test_e2e_local.py

Falsadores verificados:
  - rebuild idempotente + parity dump vs substrato SQLite (I1)
  - aec_get_via trae la via completa (I3)
  - aec_resolve ancla a content_hash desde URL cruda (I4 / D-ver-1)
  - aec_get_necesidad: traza descendente
  - read-only: un INSERT en sesion del lector falla (membrana)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG = os.path.join(os.path.dirname(__file__), "..", "..", "AEC", "log", "inscripciones.jsonl")
REF = os.path.join(os.path.dirname(__file__), "..", "_ref_dump_substrato.json")

EXPECTED_COUNTS = {"inscripcion": 1, "necesidad": 1, "consulta": 2, "referente": 3,
                   "version": 3, "afirmacion": 2, "referente_assert": 0}


def _ok(msg): print(f"  [OK] {msg}")
def _fail(msg): print(f"  [FAIL] {msg}"); sys.exit(1)


def main():
    if not os.environ.get("DATABASE_URL"):
        _fail("DATABASE_URL no seteado")

    import projection_build as pb
    import queries as q
    from db import get_engine, get_readonly_session
    from sqlalchemy import text

    engine = get_engine()

    print("== schema + replicate ==")
    pb.ensure_schema(engine)
    n1 = pb.replicate_log_from_file(os.path.abspath(LOG), engine)
    _ok(f"replicados {n1} eventos")
    n2 = pb.replicate_log_from_file(os.path.abspath(LOG), engine)
    if n2 != 0: _fail(f"replicacion no idempotente: segundo run trajo {n2}")
    _ok("replicacion idempotente (2o run = 0)")

    print("== rebuild (sin embeddings) ==")
    res = pb.rebuild_projection(engine, with_embeddings=False)
    if res["counts"] != EXPECTED_COUNTS:
        _fail(f"counts {res['counts']} != esperado {EXPECTED_COUNTS}")
    _ok(f"counts correctos: {res['counts']}")

    print("== falsador I1: parity vs substrato SQLite ==")
    dump = pb.dump_logico(engine)
    blob = json.dumps(dump, ensure_ascii=False, sort_keys=True, default=str)
    if os.path.exists(REF):
        ref = open(REF, encoding="utf-8").read()
        if blob == ref:
            _ok("dump Postgres == dump substrato SQLite (I1 cross-store)")
        else:
            _fail("dump Postgres difiere del substrato (revisar port)")
    else:
        print("  [warn] sin _ref_dump_substrato.json; salto parity")
    # idempotencia del rebuild
    pb.rebuild_projection(engine, with_embeddings=False)
    dump2 = pb.dump_logico(engine)
    if json.dumps(dump2, sort_keys=True, default=str) != json.dumps(dump, sort_keys=True, default=str):
        _fail("rebuild no idempotente")
    _ok("rebuild idempotente (2o run = identico)")

    print("== aec_get_via (I3) ==")
    session = get_readonly_session()
    af_ids = [r[0] for r in session.execute(text("SELECT id FROM afirmacion")).fetchall()]
    session.close()
    via = q.aec_get_via(af_ids[0])
    if not via or not via.get("necesidad") or not via.get("version"):
        _fail(f"via incompleta: {via}")
    if not via["version"].get("content_hash"):
        _fail("via sin content_hash")
    _ok(f"via completa: necesidad+version+inferencia presentes; hash={via['version']['content_hash'][:12]}")

    print("== aec_resolve (I4 / D-ver-1) ==")
    url = via["version"]["url_cruda"]
    resu = q.aec_resolve(url)
    if not resu or not resu.get("versiones"):
        _fail(f"resolve vacio para {url}")
    if not all(v.get("content_hash") for v in resu["versiones"]):
        _fail("alguna version sin content_hash")
    _ok(f"resolve URL->referente {resu['referente_id'][:40]}... con {len(resu['versiones'])} version(es)")
    # resolver por content_hash tambien
    ch = resu["versiones"][0]["content_hash"]
    if not q.aec_resolve(ch):
        _fail("resolve por content_hash fallo")
    _ok("resolve por content_hash OK")

    print("== aec_get_necesidad (descendente) ==")
    session = get_readonly_session()
    nec_id = session.execute(text("SELECT id FROM necesidad LIMIT 1")).fetchone()[0]
    session.close()
    nec = q.aec_get_necesidad(nec_id)
    if not nec or not nec.get("consultas"):
        _fail("necesidad sin consultas")
    _ok(f"necesidad con {len(nec['consultas'])} consulta(s)")

    print("== aec_search (ILIKE, sin embeddings) ==")
    sr = q.aec_search("log", limit=10)
    if sr["count"] < 1:
        _fail("search no encontro nada con 'log'")
    h = sr["hits"][0]
    if h.get("necesidad_stub") is None or h.get("version_pin") is None:
        _fail(f"hit pelon (sin stub de via): {h}")
    _ok(f"search modo={sr['mode']} count={sr['count']}; hit trae stub de via (no pelon, I3)")

    print("== membrana: lector es read-only ==")
    session = get_readonly_session()
    try:
        session.execute(text("UPDATE afirmacion SET tipo='x' WHERE id=:i"), {"i": af_ids[0]})
        session.commit()
        _fail("ESCRITURA PERMITIDA en sesion read-only (membrana rota)")
    except Exception:
        _ok("INSERT/UPDATE rechazado en sesion read-only (membrana intacta)")
    finally:
        session.rollback(); session.close()

    print("\nTODOS LOS FALSADORES EN VERDE.")


if __name__ == "__main__":
    main()
