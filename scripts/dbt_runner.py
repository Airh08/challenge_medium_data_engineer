"""
dbt_runner.py
=============
Ejecutor ligero de modelos dbt sobre DuckDB.

Resuelve {{ ref() }} y {{ source() }}, elimina comentarios Jinja {# ... #}
y {{ config(...) }}, y ejecuta los modelos en orden de dependencia contra
una base DuckDB.

Es compatible con la estructura de un proyecto dbt estándar — si se instala
el CLI de dbt-duckdb en el futuro, este runner puede reemplazarse directamente
por `dbt run`.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import duckdb

# ── Configuración ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = BASE_DIR / "dbt_project"
MODELS_DIR = DBT_DIR / "models"
DB_PATH = str(BASE_DIR / "data" / "kapital_creditos.duckdb")

logger = logging.getLogger(__name__)

# ── Registro de modelos: nombre → (ruta_sql, schema, dependencias) ──────────
# El orden en esta lista define el orden de ejecución (respetando dependencias).

MODELOS: list[dict[str, Any]] = [
    {
        "nombre": "stg_creditos",
        "archivo": MODELS_DIR / "staging" / "stg_creditos.sql",
        "schema": "staging",
        "deps": [],
    },
    {
        "nombre": "dim_cliente",
        "archivo": MODELS_DIR / "marts" / "dim_cliente.sql",
        "schema": "marts",
        "deps": ["stg_creditos"],
    },
    {
        "nombre": "dim_tiempo",
        "archivo": MODELS_DIR / "marts" / "dim_tiempo.sql",
        "schema": "marts",
        "deps": ["stg_creditos"],
    },
    {
        "nombre": "dim_industria",
        "archivo": MODELS_DIR / "marts" / "dim_industria.sql",
        "schema": "marts",
        "deps": ["stg_creditos"],
    },
    {
        "nombre": "fact_originaciones",
        "archivo": MODELS_DIR / "marts" / "fact_originaciones.sql",
        "schema": "marts",
        "deps": ["stg_creditos", "dim_cliente", "dim_tiempo", "dim_industria"],
    },
]


# ── Motor de resolución dbt ──────────────────────────────────────────────────


def _resolver_ref(modelo: str) -> str:
    """Resuelve {{ ref('modelo') }} → schema.modelo (fully qualified)."""
    for m in MODELOS:
        if m["nombre"] == modelo:
            return f"{m['schema']}.{modelo}"
    raise ValueError(f"Modelo no encontrado en el registro: {modelo}")


def renderizar_sql(contenido: str) -> str:
    """
    Convierte un template dbt (Jinja2) en SQL ejecutable.

    Transformaciones:
      - {{ ref('nombre') }}  →  schema.nombre
      - {{ source('src', 'tbl') }}  →  src.tbl
      - {{ config(...) }}     →  eliminado
      - {# comentario #}      →  eliminado
    """
    sql = contenido

    # 1. {{ ref('modelo') }}
    sql = re.sub(
        r"\{\{\s*ref\(\s*'([^']+)'\s*\)\s*\}\}",
        lambda m: _resolver_ref(m.group(1)),
        sql,
    )

    # 2. {{ source('source', 'tabla') }}
    sql = re.sub(
        r"\{\{\s*source\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)\s*\}\}",
        r"\1.\2",
        sql,
    )

    # 3. {{ config(...) }}
    sql = re.sub(r"\{\{\s*config\([^}]*\)\s*\}\}", "", sql)

    # 4. {# comentario dbt #}
    sql = re.sub(r"\{#[^#]*#\}", "", sql)

    return sql


# ── Ejecución contra DuckDB ──────────────────────────────────────────────────


def crear_schemas(con: duckdb.DuckDBPyConnection) -> None:
    """Crea los schemas staging y marts si no existen."""
    con.execute("CREATE SCHEMA IF NOT EXISTS staging")
    con.execute("CREATE SCHEMA IF NOT EXISTS marts")


def ejecutar_modelo(
    con: duckdb.DuckDBPyConnection,
    modelo: dict,
) -> tuple[int, float]:
    """
    Lee, renderiza y ejecuta un modelo dbt.
    Retorna (num_filas_afectadas, tiempo_segundos).
    """
    nombre = modelo["nombre"]
    schema = modelo["schema"]
    archivo = modelo["archivo"]

    logger.info("  Ejecutando modelo: %s.%s ...", schema, nombre)

    # Leer template
    with open(archivo, "r", encoding="utf-8") as f:
        template = f.read()

    # Renderizar SQL
    sql = renderizar_sql(template)

    # Ejecutar: CREATE OR REPLACE TABLE schema.modelo AS ( ... )
    ddl = f'CREATE OR REPLACE TABLE {schema}."{nombre}" AS (\n{sql}\n)'

    import time
    inicio = time.time()
    resultado = con.execute(ddl)
    fin = time.time()

    # DuckDB no devuelve rowcount directamente; consultamos COUNT(*)
    count = con.execute(
        f'SELECT COUNT(*) FROM {schema}."{nombre}"'
    ).fetchone()[0]

    duracion = fin - inicio
    logger.info("    -> %d filas en %.2fs", count, duracion)
    return count, duracion


# ── Orquestación ─────────────────────────────────────────────────────────────


def ejecutar_dbt(db_path: str | None = None) -> duckdb.DuckDBPyConnection:
    """
    Punto de entrada principal.

    Abre (o crea) la base DuckDB, crea schemas y ejecuta todos los modelos
    en orden de dependencia.
    """
    if db_path is None:
        db_path = DB_PATH

    logger.info("=" * 50)
    logger.info("DBT RUNNER — Ejecutando modelos sobre DuckDB")
    logger.info("Base de datos: %s", db_path)

    con = duckdb.connect(db_path)

    # Crear schemas
    crear_schemas(con)

    # Ejecutar modelos en orden
    total_filas = 0
    for modelo in MODELOS:
        filas, duracion = ejecutar_modelo(con, modelo)
        total_filas += filas

    logger.info("DBT RUNNER completado — %d modelos ejecutados.", len(MODELOS))
    return con


def obtener_estadisticas(con: duckdb.DuckDBPyConnection) -> dict:
    """Retorna un diccionario con el conteo de filas de cada modelo."""
    stats = {}
    for modelo in MODELOS:
        nombre = modelo["nombre"]
        schema = modelo["schema"]
        count = con.execute(
            f'SELECT COUNT(*) FROM {schema}."{nombre}"'
        ).fetchone()[0]
        stats[f"{schema}.{nombre}"] = count
    return stats


# ── Punto de entrada ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    con = ejecutar_dbt()
    stats = obtener_estadisticas(con)
    print("\nTablas creadas en el modelo dimensional:")
    for tabla, filas in stats.items():
        print(f"  {tabla:<35s} {filas:>6,} filas")
    con.close()
