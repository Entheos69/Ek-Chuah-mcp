"""
normaliza_url.py -- canonical(URL) para D-ver-1 (referente derivado, norm conservadora).

ESPEJO VENDORIZADO del contrato D-ver-1 del substrato (Ek-Chuah/normaliza_url.py,
commit 75b4ee7). Se copia -- no se importa -- porque el MCP-AEC es repo separado
(misma topologia que concept-sediment / concept-sediment-mcp). El lector usa
canonical() para resolver una URL cruda a su referente_id en aec_resolve.

CONTRATO JOINT: si CodeCS cambia la normalizacion en el substrato, este espejo
debe actualizarse (o ambos divergen y aec_resolve falla en colapsar variantes).
D-ver-1 esta ratificada (Guardian 2026-06-26); el contrato es estable.

Tres identidades, NO conflar:
  - locator  : la URL cruda (forense, muta/rota) -> se preserva aparte.
  - referente: identidad persistente del documento -> canonical(URL), este modulo.
  - contenido: content-hash = VERSION.

Solo stdlib.
"""
from __future__ import annotations
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_EXACT = {"fbclid", "gclid", "gclsrc", "dclid", "msclkid",
                   "mc_eid", "mc_cid", "igshid", "_ga"}


def _es_tracking(clave: str) -> bool:
    cl = clave.lower()
    return cl in _TRACKING_EXACT or any(cl.startswith(p) for p in _TRACKING_PREFIXES)


def canonical(url: str) -> str:
    """URL canonica conservadora. Misma pagina -> misma cadena -> mismo referente."""
    s = urlsplit(url.strip())
    scheme = "https"  # http y https de la misma pagina = mismo referente (D-ver-1)
    host = (s.hostname or "").lower()
    netloc = f"{host}:{s.port}" if s.port else host
    path = s.path or "/"
    if len(path) > 1 and path.endswith("/"):   # quitar UN trailing slash salvo raiz
        path = path.rstrip("/") or "/"
    pares = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
             if not _es_tracking(k)]
    pares.sort()                               # el orden no es identidad
    query = urlencode(pares)
    return urlunsplit((scheme, netloc, path, query, ""))  # fragmento fuera


def referente_id(url: str) -> str:
    """Identidad persistente del documento = la URL canonica (legible, grep-able)."""
    return canonical(url)
