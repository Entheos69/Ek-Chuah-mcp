"""Guard anti-recaida de pines (B.3 del handoff pin-deps 2026-07-07).

Falla si requirements.txt / constraints.txt tienen specifiers abiertos
(>=, ~=, <=, >, <, o sin version). Solo se permite pin exacto (==).

Leccion S143 (weight 1.0): escanear el TOKEN de requirement real, no
substrings en prosa/comentarios. Por eso stripeamos el comentario ANTES de
evaluar -- el comentario-vacuna de requirements.txt contiene el literal
'>=3.4.3' y un guard ingenuo por substring daria un falso positivo.
"""
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_FILES = ["requirements.txt", "constraints.txt"]


def _requirement_lines(path: Path):
    """Devuelve solo las lineas de requirement reales (sin comentarios ni opciones)."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()  # stripe comentario inline + prosa
        if not line:
            continue
        if line.startswith("-"):  # opciones de pip (-r, -c, --hash, ...)
            continue
        yield line


@pytest.mark.parametrize("fname", _FILES)
def test_deps_pineadas_con_version_exacta(fname):
    path = _REPO / fname
    assert path.exists(), f"{fname} no existe"
    ofensores = [line for line in _requirement_lines(path) if "==" not in line]
    assert not ofensores, (
        f"{fname} tiene specifiers abiertos (solo se permite pin exacto ==): "
        + ", ".join(ofensores)
    )
