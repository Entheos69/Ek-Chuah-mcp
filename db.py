"""
Ek-Chuah MCP (MCP-AEC) -- Database Connection

Conexion a PostgreSQL + pgvector via SQLAlchemy (mismo patron que
concept-sediment-mcp/db.py). Stateless: cada request crea y cierra su sesion.

DOS modos de sesion:
  - get_session():           read-write. SOLO para projection_build.py (rebuild).
  - get_readonly_session():  fuerza SET TRANSACTION READ ONLY. Es lo que usa
                             el lector C3 (server.py). Defensa en profundidad
                             del falsador membrana: "cero escritura cruzando".

El rol de BD del servicio en Railway DEBE ser un usuario solo-lectura
(defensa exterior); get_readonly_session es la defensa interior.
"""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

_engine = None
_SessionLocal = None


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError(
            "DATABASE_URL not set. Example: "
            "postgresql://user:pass@host:port/ek_chuah_aec"
        )
    # SQLAlchemy necesita 'postgresql://' no 'postgres://'
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def get_engine():
    """Obtiene o crea el engine singleton."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(
            _get_database_url(),
            pool_size=5,
            max_overflow=10,
            pool_recycle=600,
            pool_pre_ping=True,
            echo=False,
        )
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    """Sesion read-write. Caller la cierra. Solo para rebuild (projection_build)."""
    get_engine()
    return _SessionLocal()


def get_readonly_session() -> Session:
    """Sesion del lector C3: marca la transaccion como READ ONLY.

    Cualquier INSERT/UPDATE/DELETE dispara error de Postgres. Es la defensa
    en profundidad sobre el falsador "cero escritura cruzando la membrana".
    """
    get_engine()
    s = _SessionLocal()
    s.execute(text("SET TRANSACTION READ ONLY"))
    return s


def dispose_engine():
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
        _engine = None
        _SessionLocal = None


def test_connection() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"DB connection failed: {e}")
        return False
