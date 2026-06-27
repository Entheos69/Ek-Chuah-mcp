"""
embeddings.py -- proveedor de embeddings para aec_search (Gemini Embedding @1536).

Decision Guardian 2026-06-27: Gemini Embedding 001 a output_dimensionality=1536
via MRL. Razones (ver YAML de sesion): honra el rumbo sedimentado Gemini-1536
(concept-sediment, w1.0 2026-06-20); cabe en vector(1536) sin cambio de schema;
right-sized para texto (la membrana prohibe nivel-1 en la nube, asi que el lector
solo embebe texto -- el multimodal de Embedding 2 seria headroom desperdiciado);
y task types mejoran el retrieval (RETRIEVAL_DOCUMENT al indexar, RETRIEVAL_QUERY
al buscar), algo que OpenAI no distingue.

El embedding es INDICE REGENERABLE (I1): cambiar de proveedor = re-correr el
rebuild. No es puerta de un solo sentido. Por eso modelo/dim/proveedor son env-
overridable.

Distancia cosine (pgvector '<=>') es scale-invariant -> no requiere normalizar
el vector truncado por MRL.
"""
from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))

# task types validos para retrieval (Gemini)
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def available() -> bool:
    return bool(GEMINI_API_KEY)


def embed(text: str, task: str) -> list | None:
    """Embedding de un texto para una tarea de retrieval. None si no hay API key o falla.

    task: TASK_DOCUMENT (indexar afirmaciones) | TASK_QUERY (buscar).
    """
    if not GEMINI_API_KEY:
        return None
    text = (text or "").strip()
    if not text:
        return None
    try:
        from google.genai import types
        client = _get_client()
        resp = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task,
                output_dimensionality=EMBEDDING_DIM,
            ),
        )
        return list(resp.embeddings[0].values)
    except Exception as e:
        logger.warning("Gemini embedding failed (task=%s): %s", task, e)
        return None
