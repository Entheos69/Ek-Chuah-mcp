"""Guards de la logica de fallback hibrido de aec_search (puros: sin Postgres, sin Gemini).

Caza la clase de bug del incidente 2026-11-12: el fallback lexico estaba muerto mientras
existiera >=1 embedding, dejando invisibles las afirmaciones con embedding NULL. Estos tests
fijan la decision de modo/alcance y el merge, que son el nucleo del fix.
"""
from queries import _tokenize, _plan_busqueda, _merge, _ensamblar


def test_tokenize_descarta_cortos_y_conserva_acentos():
    assert _tokenize("resina epoxica") == ["resina", "epoxica"]
    assert _tokenize("CMP-BEN-886") == ["cmp", "ben", "886"]      # codigo con guiones
    assert _tokenize("de la el un") == []                          # todos < 3 chars
    assert _tokenize("formulacion epoxica AHEW") == ["formulacion", "epoxica", "ahew"]
    assert _tokenize("") == [] and _tokenize(None) == []


def test_plan_sin_embedding_del_query_cae_a_ilike():
    p = _plan_busqueda(embedding_disponible=False, n_sem=0, max_sim=None, sin_vector=True)
    assert p["mode"] == "ilike" and p["lexico"] and not p["solo_null"]


def test_plan_cero_vectores_en_base_cae_a_ilike():
    # hay embedding del query pero ninguna afirmacion tiene vector -> n_sem == 0
    p = _plan_busqueda(embedding_disponible=True, n_sem=0, max_sim=None, sin_vector=True)
    assert p["mode"] == "ilike" and p["lexico"]


def test_plan_bajo_umbral_activa_lexico_sobre_todo_y_primero():
    # el sintoma real: semantico devuelve hardware a ~0.51 para un query de adhesivos
    p = _plan_busqueda(embedding_disponible=True, n_sem=10, max_sim=0.51, sin_vector=True)
    assert p["mode"] == "embedding_bajo_umbral"
    assert p["lexico"] and p["lexico_primero"] and not p["solo_null"]


def test_plan_sano_con_nulls_es_hibrido_solo_null():
    p = _plan_busqueda(embedding_disponible=True, n_sem=10, max_sim=0.72, sin_vector=True)
    assert p["mode"] == "hibrido"
    assert p["lexico"] and p["solo_null"] and not p["lexico_primero"]


def test_plan_sano_cobertura_total_es_embedding_puro():
    p = _plan_busqueda(embedding_disponible=True, n_sem=10, max_sim=0.72, sin_vector=False)
    assert p["mode"] == "embedding" and not p["lexico"]


def test_plan_umbral_es_estricto():
    # exactamente en el umbral NO es bajo_umbral
    p = _plan_busqueda(True, 10, 0.60, sin_vector=False, umbral=0.60)
    assert p["mode"] == "embedding"
    p2 = _plan_busqueda(True, 10, 0.5999, sin_vector=False, umbral=0.60)
    assert p2["mode"] == "embedding_bajo_umbral"


def test_merge_dedup_y_prioridad():
    sem = [{"af_id": "a"}, {"af_id": "b"}]
    lex = [{"af_id": "b"}, {"af_id": "c"}]       # 'b' aparece en ambos
    assert [h["af_id"] for h in _merge(sem, lex, 10, lexico_primero=False)] == ["a", "b", "c"]
    assert [h["af_id"] for h in _merge(sem, lex, 10, lexico_primero=True)] == ["b", "c", "a"]


def test_merge_respeta_limit():
    sem = [{"af_id": str(i)} for i in range(5)]
    assert len(_merge(sem, [], 3, lexico_primero=False)) == 3


def test_ensamblar_filtra_cola_debil_a_vecinos_aun_en_modo_embedding():
    # el caso CMP-BEN-886 real: el top esta sobre umbral (mode=embedding), pero la COLA
    # (0.59 CRM/CSS) esta debajo -> no debe salir como `hits`, va a vecinos_debiles.
    plan = {"mode": "embedding"}
    sem = [{"af_id": "fuerte", "similarity": 0.72}, {"af_id": "ruido", "similarity": 0.59}]
    r = _ensamblar(plan, sem, [], {"total": 9}, limit=5, umbral=0.60)
    assert [h["af_id"] for h in r["hits"]] == ["fuerte"]
    assert [h["af_id"] for h in r["vecinos_debiles"]] == ["ruido"]


def test_ensamblar_todo_debil_sin_lexico_devuelve_vacio():
    # sin nada sobre umbral ni grano lexico: `hits` vacio (no fingir 'encontre').
    plan = {"mode": "embedding_bajo_umbral"}
    sem = [{"af_id": "ruido1", "similarity": 0.59}, {"af_id": "ruido2", "similarity": 0.55}]
    r = _ensamblar(plan, sem, [], {"total": 9}, limit=5, umbral=0.60)
    assert r["count"] == 0 and r["hits"] == []
    assert [h["af_id"] for h in r["vecinos_debiles"]] == ["ruido1", "ruido2"]


def test_ensamblar_todo_debil_con_lexico_manda_el_lexico():
    plan = {"mode": "embedding_bajo_umbral"}
    sem = [{"af_id": "ruido", "similarity": 0.58}]
    lex = [{"af_id": "preciso"}]
    r = _ensamblar(plan, sem, lex, {"total": 9}, limit=5, umbral=0.60)
    assert [h["af_id"] for h in r["hits"]] == ["preciso"]
    assert [h["af_id"] for h in r["vecinos_debiles"]] == ["ruido"]


def test_ensamblar_todo_fuerte_sin_vecinos():
    plan = {"mode": "embedding"}
    sem = [{"af_id": "a", "similarity": 0.8}, {"af_id": "b", "similarity": 0.7}]
    r = _ensamblar(plan, sem, [], {"total": 9}, limit=5, umbral=0.60)
    assert [h["af_id"] for h in r["hits"]] == ["a", "b"]
    assert "vecinos_debiles" not in r
