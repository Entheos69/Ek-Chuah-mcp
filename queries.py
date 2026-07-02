"""
Ek-Chuah MCP (MCP-AEC) -- Queries del lector C3 (read-only).

Lectura sobre graph_aec en Postgres. TODA sesion es get_readonly_session
(SET TRANSACTION READ ONLY): defensa en profundidad del falsador membrana.

Las 4 funciones son ports de Ek-Chuah/proyeccion.py al lector nube:
  - aec_get_via      <- traza_ascendente   (I3: leer trae el porque)
  - aec_resolve      <- version_actual + normaliza_url (I4 / D-ver-1)
  - aec_search        : indice anti-re-investigacion (pgvector + fallback ILIKE)
  - aec_get_necesidad : traza descendente (que trajo una indagacion y que sobrevivio)

MEMBRANA: ninguna funcion lee snapshots (nivel 1). Se devuelve content_hash,
nunca bytes. Aqui NO se importa nada que toque AEC/snapshots.
"""
import logging
from typing import Optional

from sqlalchemy import text

from db import get_readonly_session
from normaliza_url import canonical
from embeddings import embed, TASK_QUERY

logger = logging.getLogger(__name__)


def _generate_query_embedding(query_text: str) -> list | None:
    """Embedding del query con task type RETRIEVAL_QUERY (asimetria de retrieval)."""
    return embed(query_text, TASK_QUERY)


# ════════════════════════════════════════════════════════════════
# aec_search -- reconocimiento barato; hit con STUB de via, nunca pelon
# ════════════════════════════════════════════════════════════════

_SEARCH_SELECT = """
    SELECT a.id AS af_id, a.txt, a.tipo, a.estatus,
           v.referente_id, v.content_hash, v.capture_ts,
           n.pregunta, n.gatillo {sim}
    FROM afirmacion a
    LEFT JOIN version v   ON v.id = a.ref_id
    LEFT JOIN consulta c  ON c.id = v.q_id
    LEFT JOIN necesidad n ON n.id = c.nec_id
"""


def _hit_from_row(row, with_sim: bool) -> dict:
    hit = {
        "af_id": row.af_id,
        "txt": row.txt,
        "tipo": row.tipo,
        "estatus": row.estatus,
        "version_pin": {
            "referente_id": row.referente_id,
            "content_hash": row.content_hash,
            "capture_ts": row.capture_ts,
        } if row.referente_id else None,
        "necesidad_stub": {
            "pregunta": row.pregunta,
            "gatillo": row.gatillo,
        } if row.pregunta else None,
    }
    if with_sim:
        hit["similarity"] = round(row.similarity, 4)
    return hit


def aec_search(query: str, limit: int = 10, include_superadas: bool = False) -> dict:
    """Indice anti-re-investigacion. Embedding (pgvector) con fallback ILIKE.

    Cada hit trae stub de via (necesidad + pin de version) -- NUNCA un dato pelon (I3).
    La via completa se expande on-demand con aec_get_via.

    G-post: por defecto excluye afirmaciones superadas/retractadas (solo estatus='afirmado')
    -- una reconsideracion no debe re-aparecer como saber vigente. include_superadas=True
    las trae (historia; Forma-vs-Valor: se conservan, no se borran).
    """
    # el estatus efectivo ya lo dejo aplicado el rebuild (la revision volteo afirmacion.estatus)
    est = "" if include_superadas else " AND a.estatus = 'afirmado'"
    embedding = _generate_query_embedding(query)
    session = get_readonly_session()
    try:
        if embedding:
            vec = "[" + ",".join(str(f) for f in embedding) + "]"
            sql = _SEARCH_SELECT.format(
                sim=", 1 - (a.embedding <=> CAST(:vec AS vector)) AS similarity")
            sql += (" WHERE a.embedding IS NOT NULL" + est +
                    " ORDER BY a.embedding <=> CAST(:vec AS vector) ASC LIMIT :limit")
            rows = session.execute(text(sql), {"vec": vec, "limit": limit}).fetchall()
            if rows:
                return {"count": len(rows), "mode": "embedding",
                        "hits": [_hit_from_row(r, True) for r in rows]}

        # fallback ILIKE sobre el texto de la afirmacion
        sql = _SEARCH_SELECT.format(sim="")
        sql += " WHERE a.txt ILIKE :pat" + est + " ORDER BY a.ts DESC LIMIT :limit"
        rows = session.execute(text(sql), {"pat": f"%{query}%", "limit": limit}).fetchall()
        return {"count": len(rows), "mode": "ilike",
                "hits": [_hit_from_row(r, False) for r in rows]}
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# aec_get_via -- via ascendente completa (I3). Port de traza_ascendente.
# ════════════════════════════════════════════════════════════════

def aec_get_via(af_id: str) -> dict | None:
    """De una afirmacion a la necesidad que la engendro -- la via completa (I3)."""
    session = get_readonly_session()
    try:
        a = session.execute(text(
            "SELECT * FROM afirmacion WHERE id=:id"), {"id": af_id}).fetchone()
        if a is None:
            return None
        out = {
            "afirmacion": {"af_id": a.id, "txt": a.txt, "tipo": a.tipo, "estatus": a.estatus},
            "inferencia": None, "version": None, "consulta": None, "necesidad": None,
        }
        # G-post: si la afirmacion fue reconsiderada, trae su historial auditado (I3 extendido:
        # leer trae tambien el porque dejo de sostenerse).
        if a.estatus != "afirmado":
            revs = session.execute(text(
                "SELECT nuevo_estatus, reemplazada_por, motivo, gatillo FROM revision "
                "WHERE target_af=:id ORDER BY ts ASC"), {"id": af_id}).fetchall()
            out["reconsideracion"] = [
                {"nuevo_estatus": r.nuevo_estatus, "reemplazada_por": r.reemplazada_por,
                 "motivo": r.motivo, "gatillo": r.gatillo} for r in revs]
        if a.insc_id:
            i = session.execute(text(
                "SELECT * FROM inscripcion WHERE id=:id"), {"id": a.insc_id}).fetchone()
            if i:
                out["inferencia"] = {
                    "conclusion": i.conclusion,
                    "inferida_por": f"{i.inferidor_model}@{i.inferidor_ts}",
                    "huella": (i.huella or "")[:12],
                }
        if a.ref_id:
            v = session.execute(text(
                "SELECT * FROM version WHERE id=:id"), {"id": a.ref_id}).fetchone()
            if v:
                out["version"] = {
                    "referente_id": v.referente_id, "content_hash": v.content_hash,
                    "url_cruda": v.url_cruda, "capture_ts": v.capture_ts,
                    "estatus_ref": v.estatus or "viva",
                }
                q = session.execute(text(
                    "SELECT * FROM consulta WHERE id=:id"), {"id": v.q_id}).fetchone()
                if q:
                    out["consulta"] = q.formulacion
                    n = session.execute(text(
                        "SELECT * FROM necesidad WHERE id=:id"), {"id": q.nec_id}).fetchone()
                    if n:
                        out["necesidad"] = {
                            "pregunta": n.pregunta, "gatillo": n.gatillo, "ancla": n.origen_nodo,
                        }
        return out
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# aec_resolve -- capa de acceso D-ver-1: url | referente_id | content_hash
# ════════════════════════════════════════════════════════════════

def aec_resolve(locator: str) -> dict | None:
    """Resuelve un referente a su cadena de versiones (I4) + que se afirmo de cada una.

    Acepta URL cruda (la normaliza a referente_id), referente_id, o content_hash.
    Vista default = ultima version por capture_ts (D-ver-3); las afirmaciones
    conservan su pin.
    """
    session = get_readonly_session()
    try:
        loc = (locator or "").strip()

        # 1) content_hash exacto -> resolver su referente
        ref_id = None
        if loc.startswith("sha256:") or (len(loc) == 64 and all(c in "0123456789abcdef" for c in loc.lower())):
            h = loc.split("sha256:", 1)[-1]
            v = session.execute(text(
                "SELECT referente_id FROM version WHERE content_hash=:h LIMIT 1"),
                {"h": h}).fetchone()
            if v:
                ref_id = v.referente_id

        # 2) referente_id directo (existe tal cual)
        if ref_id is None:
            r = session.execute(text(
                "SELECT referente_id FROM referente WHERE referente_id=:r"),
                {"r": loc}).fetchone()
            if r:
                ref_id = r.referente_id

        # 3) URL cruda -> canonical -> referente_id (D-ver-1)
        if ref_id is None:
            cand = canonical(loc)
            r = session.execute(text(
                "SELECT referente_id FROM referente WHERE referente_id=:r"),
                {"r": cand}).fetchone()
            if r:
                ref_id = r.referente_id

        if ref_id is None:
            return None

        versions = session.execute(text(
            "SELECT id, content_hash, capture_ts, estatus FROM version "
            "WHERE referente_id=:r ORDER BY capture_ts DESC, id DESC"),
            {"r": ref_id}).fetchall()

        out_versions = []
        for v in versions:
            afs = session.execute(text(
                "SELECT id FROM afirmacion WHERE ref_id=:vid"), {"vid": v.id}).fetchall()
            out_versions.append({
                "content_hash": v.content_hash,
                "capture_ts": v.capture_ts,
                "estatus": v.estatus or "viva",
                "afirmaciones": [a.id for a in afs],
            })

        return {"referente_id": ref_id, "vista_default": "ultima", "versiones": out_versions}
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# aec_get_necesidad -- traza descendente: que trajo una indagacion y que sobrevivio
# ════════════════════════════════════════════════════════════════

def aec_get_necesidad(nec_id: str) -> dict | None:
    """De una necesidad hacia abajo: consultas -> referencias -> afirmaciones."""
    session = get_readonly_session()
    try:
        n = session.execute(text(
            "SELECT * FROM necesidad WHERE id=:id"), {"id": nec_id}).fetchone()
        if n is None:
            return None

        consultas = session.execute(text(
            "SELECT * FROM consulta WHERE nec_id=:id ORDER BY ts ASC"),
            {"id": nec_id}).fetchall()

        out_consultas = []
        for c in consultas:
            versiones = session.execute(text(
                "SELECT * FROM version WHERE q_id=:q ORDER BY capture_ts ASC"),
                {"q": c.id}).fetchall()
            refs = []
            for v in versiones:
                afs = session.execute(text(
                    "SELECT txt FROM afirmacion WHERE ref_id=:vid"), {"vid": v.id}).fetchall()
                refs.append({
                    "url": v.url_cruda,
                    "referente_id": v.referente_id,
                    "content_hash": v.content_hash,
                    "sobrevivio": [a.txt for a in afs],
                })
            out_consultas.append({"formulacion": c.formulacion, "referencias": refs})

        return {
            "nec_id": n.id,
            "necesidad": n.pregunta,
            "gatillo": n.gatillo,
            "ancla": n.origen_nodo,
            "consultas": out_consultas,
        }
    finally:
        session.close()
