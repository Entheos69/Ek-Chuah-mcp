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
  - aec_search recall: ILIKE por terminos + cobertura_embedding (incidente 2026-11-12,
    SOL Cowork->CodeAEC): el fallback no debe quedar ciego cuando el embedding es NULL
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG = os.path.join(os.path.dirname(__file__), "..", "..", "AEC", "log", "inscripciones.jsonl")
REF = os.path.join(os.path.dirname(__file__), "..", "_ref_dump_substrato.json")

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

    # Verdad esperada = el dump del substrato (self-updating: se regenera cuando el log
    # crece o cambia el schema). Evita re-hardcodear counts que driftean con cada grano.
    ref = open(REF, encoding="utf-8").read() if os.path.exists(REF) else None
    expected_counts = ({t: len(rows) for t, rows in json.loads(ref)} if ref else None)

    print("== rebuild (sin embeddings) ==")
    res = pb.rebuild_projection(engine, with_embeddings=False)
    if expected_counts is not None and res["counts"] != expected_counts:
        _fail(f"counts {res['counts']} != esperado (substrato) {expected_counts}")
    _ok(f"counts correctos: {res['counts']}")

    print("== falsador I1: parity vs substrato SQLite ==")
    dump = pb.dump_logico(engine)
    blob = json.dumps(dump, ensure_ascii=False, sort_keys=True, default=str)
    if ref is not None:
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

    print("== aec_search recall: ILIKE por terminos + cobertura (regresion 2026-11-12) ==")
    # cobertura_embedding SIEMPRE presente (dir. 12: silencio != ausencia)
    if "cobertura_embedding" not in sr:
        _fail("aec_search no reporta cobertura_embedding")
    _ok(f"cobertura_embedding presente: {sr['cobertura_embedding']}")

    # El bug: con embedding NULL, el ILIKE por SUBCADENA COMPLETA no casaba multi-palabra,
    # y el `if rows:` del pase semantico dejaba muerto el fallback. Ahora el ILIKE es por
    # TERMINOS. Tomamos el txt de una afirmacion, barajamos sus palabras + ruido, y exigimos
    # reencontrarla (el codigo viejo fallaba este caso).
    import re as _re
    session = get_readonly_session()
    sample = session.execute(text(
        "SELECT id, txt FROM afirmacion WHERE length(txt) > 40 AND estatus='afirmado' "
        "ORDER BY id LIMIT 1")).fetchone()
    session.close()
    toks = [t for t in _re.findall(r"\w+", sample.txt.lower()) if len(t) >= 4][:4]
    query_barajada = "contexto irrelevante " + " ".join(reversed(toks))
    if not any(h["af_id"] == sample.id for h in q.aec_search(query_barajada, limit=20)["hits"]):
        _fail(f"fallback por terminos no reencontro {sample.id[:8]} con {query_barajada!r}")
    _ok(f"fallback por terminos reencuentra {sample.id[:8]} pese a orden/ruido")

    # Criterio §4 del SOL: la consulta de Ancamide devuelve abfcc728 en el top-5 (si el log
    # de este entorno lo contiene; si no, se salta sin fallar).
    ABF = "abfcc728e86eaa49af56d74fe407789809ea9f63dae184f29498a4535d41a16b"
    session = get_readonly_session()
    has_abf = session.execute(text("SELECT 1 FROM afirmacion WHERE id=:i"), {"i": ABF}).fetchone()
    session.close()
    if has_abf:
        top5 = [h["af_id"] for h in q.aec_search(
            "Ancamide 2353 poliamida endurecedor AHEW gel time hoja tecnica", limit=5)["hits"]]
        if ABF not in top5:
            _fail(f"consulta Ancamide no trajo abfcc728 en top-5: {[x[:8] for x in top5]}")
        _ok("consulta Ancamide -> abfcc728 en top-5 (SOL Cowork 2026-11-12, criterio §4)")
    else:
        print("  [warn] abfcc728 no esta en este log; salto el criterio §4 especifico")

    print("== G-post: reconsideracion (revision) sobre Postgres ==")
    target = af_ids[0]
    rev_ev = {"ev": "revision", "id": "e2e-rev-1", "target_af": target,
              "nuevo_estatus": "superada", "reemplazada_por": None,
              "motivo": "e2e", "gatillo": "explicito:'e2e'", "ts": "2026-07-02T00:00:00"}
    with engine.begin() as cx:
        cx.execute(text("INSERT INTO aec_log (line_sha, event) VALUES (:s, CAST(:e AS jsonb)) "
                        "ON CONFLICT (line_sha) DO NOTHING"),
                   {"s": pb._line_sha(rev_ev), "e": pb._canon_line(rev_ev)})
    pb.rebuild_projection(engine, with_embeddings=False)
    session = get_readonly_session()
    est = session.execute(text("SELECT estatus FROM afirmacion WHERE id=:i"),
                          {"i": target}).fetchone()[0]
    session.close()
    if est != "superada":
        _fail(f"revision no volteo el estatus en Postgres: {est}")
    via2 = q.aec_get_via(target)
    if not via2.get("reconsideracion"):
        _fail("aec_get_via no expone el historial de reconsideracion")
    # la superada sale de la vista por default; incluible con include_superadas
    txt = via2["afirmacion"]["txt"]
    if any(h["af_id"] == target for h in q.aec_search(txt, limit=20)["hits"]):
        _fail("aec_search devolvio una afirmacion superada por default")
    _ok("revision voltea estatus + aec_get_via trae historial + aec_search la excluye (G-post)")

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
