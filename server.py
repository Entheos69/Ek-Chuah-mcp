"""
Ek-Chuah MCP -- MCP-AEC (lector C3 del Archivo Epistemico en la nube)

Servidor MCP read-only (Streamable HTTP) que sirve graph_aec: cualquier IA lee
la via epistemica autonoma, y por I3 cada lectura trae su porque.

4 tools (TODAS read-only -- no hay write path; aportar va por Estratega fuera de aqui):
  - aec_search        : "ya investigue X?" indice anti-re-investigacion (embeddings + ILIKE)
  - aec_get_via       : una afirmacion + su via ascendente completa (I3)
  - aec_resolve       : un referente -> su cadena de versiones (I4) + que se afirmo
  - aec_get_necesidad : traza descendente -- que trajo una indagacion y que sobrevivio

5a tool aec_divergencia DIFERIDA (LECTOR_C3 §8): activar cuando haya inferidor real
Y >=1 huella con lecturas multiples. Hoy no hay insumo.

Membrana (DISENO §2, honrada en el lector):
  - no escribe (read-only por construccion + get_readonly_session)
  - no baja URLs (sin web; la url es metadato forense)
  - no sirve nivel 1 (devuelve content_hash, nunca bytes del snapshot)

Camino B (Guardian 2026-06-27): graph_aec es proyeccion regenerable del log
replicado (aec_log). Reconstruccion: projection_build.py (CLI o boot).

Uso:
  python server.py
  DATABASE_URL=postgresql://... OPENAI_API_KEY=... python server.py
  AEC_REBUILD_ON_BOOT=1 python server.py   # reconstruye graph_aec de aec_log al arrancar
"""
import json
import logging
import os
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from db import get_engine, dispose_engine
from queries import aec_search, aec_get_via, aec_resolve, aec_get_necesidad

MCP_PORT = int(os.environ.get("MCP_PORT", os.environ.get("PORT", "8000")))
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("ek_chuah_mcp")


@asynccontextmanager
async def app_lifespan(server):
    engine = get_engine()
    if os.environ.get("AEC_REBUILD_ON_BOOT") == "1":
        # camino B: la proyeccion es regenerable del log replicado.
        from projection_build import ensure_schema, rebuild_projection
        ensure_schema(engine)
        rebuild_projection(engine, with_embeddings=True)
        logger.info("graph_aec reconstruido de aec_log al arrancar")
    yield {"engine": engine}
    dispose_engine()


mcp = FastMCP("ek_chuah_mcp", lifespan=app_lifespan)


_RO = {"title": "", "readOnlyHint": True, "destructiveHint": False,
       "idempotentHint": True, "openWorldHint": False}


def _ann(title: str) -> dict:
    a = dict(_RO)
    a["title"] = title
    return a


# ════════════════════════════════════════════════════════════════
# TOOL 1: aec_search
# ════════════════════════════════════════════════════════════════

class SearchInput(BaseModel):
    """Parametros para el indice anti-re-investigacion."""
    query: str = Field(..., description="Tema o pregunta: '?ya investigue X?'",
                       min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    format: str = Field(default="json", description="'json' | 'markdown'")


@mcp.tool(name="aec_search", annotations=_ann("AEC Search (anti-re-investigation index)"))
def t_aec_search(params: SearchInput) -> str:
    """Busca en el AEC si una pregunta ya fue investigada (indice anti-re-investigacion).

    Usa embeddings (pgvector) con fallback ILIKE. Cada hit trae un STUB de via
    (la necesidad de la que nacio + el pin de version al que esta anclado) --
    NUNCA un dato pelon (I3). Expande la via completa con aec_get_via(af_id).
    """
    return json.dumps(aec_search(params.query, params.limit),
                      ensure_ascii=False, indent=2, default=str)


# ════════════════════════════════════════════════════════════════
# TOOL 2: aec_get_via
# ════════════════════════════════════════════════════════════════

class GetViaInput(BaseModel):
    """Parametros para expandir la via completa de una afirmacion."""
    af_id: str = Field(..., description="id de la afirmacion (de aec_search)", min_length=1)


@mcp.tool(name="aec_get_via", annotations=_ann("AEC Get Via (epistemic chain, I3)"))
def t_aec_get_via(params: GetViaInput) -> str:
    """Devuelve una afirmacion con su VIA ASCENDENTE completa (I3 -- leer trae el porque).

    Cadena: afirmacion -> inferencia(firmada) -> version(content_hash) ->
    consulta -> necesidad(gatillo). Es el candado de diseno: nunca un dato sin
    su porque. No entrega bytes de nivel 1, solo el content_hash de la version.
    """
    data = aec_get_via(params.af_id)
    if data is None:
        return json.dumps({"error": f"afirmacion no encontrada: '{params.af_id}'"},
                          ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ════════════════════════════════════════════════════════════════
# TOOL 3: aec_resolve
# ════════════════════════════════════════════════════════════════

class ResolveInput(BaseModel):
    """Parametros para resolver un referente (D-ver-1)."""
    locator: str = Field(..., description="URL cruda | referente_id | content_hash",
                         min_length=1)


@mcp.tool(name="aec_resolve", annotations=_ann("AEC Resolve (version chain, I4)"))
def t_aec_resolve(params: ResolveInput) -> str:
    """Resuelve un referente a su cadena de versiones (I4) + que se afirmo de cada una.

    Acepta URL cruda (la normaliza a referente_id, D-ver-1), referente_id directo,
    o content_hash (version exacta). Vista default = ultima version (D-ver-3); cada
    afirmacion conserva su pin a content_hash, nunca a la URL mutable.
    """
    data = aec_resolve(params.locator)
    if data is None:
        return json.dumps({"error": f"referente no encontrado: '{params.locator}'"},
                          ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ════════════════════════════════════════════════════════════════
# TOOL 4: aec_get_necesidad
# ════════════════════════════════════════════════════════════════

class GetNecesidadInput(BaseModel):
    """Parametros para la traza descendente de una necesidad."""
    nec_id: str = Field(..., description="id de la necesidad", min_length=1)


@mcp.tool(name="aec_get_necesidad", annotations=_ann("AEC Get Necesidad (descending trace)"))
def t_aec_get_necesidad(params: GetNecesidadInput) -> str:
    """Traza descendente: que trajo una indagacion y que sobrevivio.

    De una necesidad hacia abajo: consultas -> referencias(version) ->
    afirmaciones que sobrevivieron de cada referencia. La cara espejo de aec_get_via.
    """
    data = aec_get_necesidad(params.nec_id)
    if data is None:
        return json.dumps({"error": f"necesidad no encontrada: '{params.nec_id}'"},
                          ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ── App con health check + MCP ──
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def health(request):
    return JSONResponse({
        "status": "ok",
        "service": "ek_chuah_mcp",
        "version": "0.1.0",
    })


mcp_http = mcp.http_app()

app = Starlette(
    routes=[Route("/health", health)],
    lifespan=mcp_http.lifespan,
)
app.mount("/", mcp_http)

if __name__ == "__main__":
    import uvicorn
    print(f"Ek-Chuah MCP (MCP-AEC) -- on {MCP_HOST}:{MCP_PORT}")
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
