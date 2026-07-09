"""
Guard: ningun INSERT del rebuild puede ser posicional.

Incidente 2026-07-08: `version.estatus` llego por ALTER TABLE (G-post). En la BD
ya desplegada la columna se anexa AL FINAL, no en la posicion que le da el
CREATE TABLE de schema.sql. Un `INSERT INTO version VALUES (...)` posicional
escribia entonces `viva` en `ts` y el timestamp en `estatus`, corrompiendo el
falsador I2 (cero referencia load-bearing sin snapshot) en produccion.

El fix no es reordenar: es nombrar las columnas. Este test lo mantiene cerrado
para toda tabla presente y futura, sin necesitar Postgres.
"""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "projection_build.py"

# "INSERT INTO <tabla> VALUES" -- sin lista de columnas entre el nombre y VALUES.
POSICIONAL = re.compile(r"INSERT\s+INTO\s+(\w+)\s+VALUES", re.IGNORECASE)

# "INSERT INTO <tabla> (col,col,...)" -- la forma sancionada.
NOMBRADO = re.compile(r"INSERT\s+INTO\s+(\w+)\s*\(", re.IGNORECASE)


def _sql_concatenado() -> str:
    """El SQL vive partido en literales adyacentes; unelos para poder matchear."""
    src = FUENTE.read_text(encoding="utf-8")
    return re.sub(r'"\s*\n\s*"', "", src)


def test_ningun_insert_posicional():
    sql = _sql_concatenado()
    posicionales = POSICIONAL.findall(sql)
    assert not posicionales, (
        "INSERT posicional en projection_build.py sobre: "
        f"{sorted(set(posicionales))}. Nombra las columnas: un ALTER TABLE "
        "posterior anexa al final y permuta los valores en la BD desplegada."
    )


def test_todas_las_tablas_de_proyeccion_se_pueblan_por_nombre():
    sql = _sql_concatenado()
    nombradas = {t.lower() for t in NOMBRADO.findall(sql)}
    # `referente` tambien recibe un UPDATE; basta con que su INSERT sea nombrado.
    esperadas = {
        "inscripcion", "necesidad", "consulta", "referente",
        "version", "afirmacion", "referente_assert", "revision",
    }
    faltantes = esperadas - nombradas
    assert not faltantes, f"tablas sin INSERT con columnas nombradas: {sorted(faltantes)}"
