#!/usr/bin/env python3
"""
02_load_and_transform.py
=========================
Script de ETL ejecutado por el contenedor `etl` (Python 3.12).
Espera a que las tablas estén creadas por PostgreSQL initdb, luego
carga el CSV en raw y transforma al modelo estrella (staging + marts).
"""

import csv
import os
import sys
import time
from datetime import datetime

import psycopg2
from psycopg2 import errors

# ── Configuración ────────────────────────────────────────────────────────────

CSV_PATH = "/data/creditos_mes.csv"
PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_DB = os.environ.get("POSTGRES_DB", "kapital_creditos")
PG_USER = os.environ.get("POSTGRES_USER", "kapital")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "kapital2025")

MONTO_MIN = 1_000
MONTO_MAX = 5_000_000
MAX_RETRIES = 30
RETRY_DELAY = 2  # segundos


# ── Utilidades ───────────────────────────────────────────────────────────────


def conectar():
    """Establece conexión a PostgreSQL con reintentos."""
    for intento in range(1, MAX_RETRIES + 1):
        try:
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname=PG_DB,
                user=PG_USER,
                password=PG_PASS,
            )
            conn.autocommit = True
            print(f"[ETL] Conexion establecida en intento {intento}.")
            return conn
        except psycopg2.OperationalError as e:
            print(f"[ETL] Intento {intento}/{MAX_RETRIES}: PostgreSQL no listo "
                  f"({e}). Esperando {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
    raise RuntimeError(
        f"No se pudo conectar a PostgreSQL tras {MAX_RETRIES} intentos."
    )


def esperar_tablas(conn):
    """Espera a que las tablas del modelo existan (initdb puede estar corriendo)."""
    tablas_requeridas = [
        ("marts", "fact_originaciones"),
        ("marts", "dim_cliente"),
        ("marts", "dim_tiempo"),
        ("marts", "dim_industria"),
        ("staging", "stg_creditos"),
        ("raw", "raw_creditos"),
    ]
    cur = conn.cursor()
    for intento in range(1, MAX_RETRIES + 1):
        try:
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema IN ('raw', 'staging', 'marts')
            """)
            existentes = set((r[0], r[1]) for r in cur.fetchall())
            faltantes = [t for t in tablas_requeridas if t not in existentes]
            if not faltantes:
                cur.close()
                print(f"[ETL] Todas las tablas existen (intento {intento}).")
                return
            print(f"[ETL] Intento {intento}/{MAX_RETRIES}: esperando "
                  f"{len(faltantes)} tablas: {[f'{s}.{t}' for s, t in faltantes]}")
        except Exception as e:
            print(f"[ETL] Intento {intento}/{MAX_RETRIES}: error consultando "
                  f"information_schema: {e}")
        time.sleep(RETRY_DELAY)
    cur.close()
    raise RuntimeError("Las tablas no se crearon a tiempo. Revisa los logs de postgres.")


def crear_funciones_seguras(conn):
    """Crea funciones try_cast_* equivalentes a TRY_CAST de DuckDB.
    Se ejecutan aquí (no en initdb) para garantizar que existen."""
    cur = conn.cursor()
    cur.execute("""
        CREATE OR REPLACE FUNCTION try_cast_date(txt TEXT) RETURNS DATE AS $$
        BEGIN
            RETURN CAST(txt AS DATE);
        EXCEPTION WHEN OTHERS THEN
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)
    cur.execute("""
        CREATE OR REPLACE FUNCTION try_cast_double(txt TEXT)
        RETURNS DOUBLE PRECISION AS $$
        BEGIN
            RETURN CAST(txt AS DOUBLE PRECISION);
        EXCEPTION WHEN OTHERS THEN
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)
    cur.execute("""
        CREATE OR REPLACE FUNCTION try_cast_integer(txt TEXT) RETURNS INTEGER AS $$
        BEGIN
            RETURN CAST(txt AS INTEGER);
        EXCEPTION WHEN OTHERS THEN
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)
    cur.close()
    print("[ETL] Funciones try_cast_* creadas.")


def truncar_todo(conn):
    """Limpia todas las tablas para ejecución idempotente."""
    cur = conn.cursor()
    tablas = [
        "marts.fact_originaciones",
        "marts.dim_cliente",
        "marts.dim_tiempo",
        "marts.dim_industria",
        "staging.stg_creditos",
        "raw.raw_creditos",
    ]
    for tabla in tablas:
        try:
            cur.execute(f"TRUNCATE TABLE {tabla} CASCADE")
        except Exception as e:
            print(f"[ETL]  WARNING al truncar {tabla}: {e}")
    cur.close()
    print("[ETL] Tablas truncadas para carga limpia.")


# ── 1. Carga del CSV a raw ─────────────────────────────────────────────────


def cargar_raw(conn):
    """Carga creditos_mes.csv en raw.raw_creditos."""
    cur = conn.cursor()

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    sql = """
        INSERT INTO raw.raw_creditos
            (id_credito, fecha_originacion, id_cliente, nombre_cliente,
             industria, monto, plazo_meses, canal, estatus_primer_pago)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    data = [
        (
            r["id_credito"],
            r["fecha_originacion"],
            r["id_cliente"],
            r["nombre_cliente"],
            r["industria"],
            r["monto"],
            r["plazo_meses"],
            r["canal"],
            r["estatus_primer_pago"],
        )
        for r in rows
    ]
    cur.executemany(sql, data)
    count = cur.rowcount
    cur.close()
    print(f"[INIT] {count} registros cargados en raw.raw_creditos")
    return count


# ── 2. Staging: limpieza, tipado, deduplicación ─────────────────────────────


def transformar_staging(conn):
    """Limpia y carga datos en staging.stg_creditos."""
    cur = conn.cursor()
    sql = """
        INSERT INTO staging.stg_creditos
        WITH filtered AS (
            SELECT *
            FROM raw.raw_creditos
            WHERE id_credito IS NOT NULL
              AND id_credito != ''
              AND fecha_originacion IS NOT NULL
              AND fecha_originacion != ''
              AND monto IS NOT NULL
              AND monto != ''
        ),
        typed AS (
            SELECT
                id_credito,
                try_cast_date(fecha_originacion)      AS fecha_originacion,
                id_cliente,
                nombre_cliente,
                industria,
                try_cast_double(monto)                 AS monto,
                try_cast_integer(NULLIF(plazo_meses, '')) AS plazo_meses,
                canal,
                estatus_primer_pago
            FROM filtered
        ),
        valid AS (
            SELECT *
            FROM typed
            WHERE fecha_originacion IS NOT NULL
              AND monto IS NOT NULL
              AND monto >= 1000
              AND monto <= 5000000
        ),
        dedup AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY id_credito
                    ORDER BY fecha_originacion
                ) AS rn
            FROM valid
        )
        SELECT
            id_credito, fecha_originacion, id_cliente, nombre_cliente,
            industria, monto, plazo_meses, canal, estatus_primer_pago
        FROM dedup
        WHERE rn = 1
    """
    cur.execute(sql)
    count = cur.rowcount
    cur.close()
    print(f"[INIT] {count} registros en staging.stg_creditos")
    return count


# ── 3. Dimensiones y fact table ──────────────────────────────────────────────


def construir_dimensiones(conn):
    """Construye dim_cliente, dim_tiempo, dim_industria a partir del staging."""
    cur = conn.cursor()

    # dim_cliente
    cur.execute("""
        INSERT INTO marts.dim_cliente (cliente_id, id_cliente, nombre_cliente)
        SELECT
            ROW_NUMBER() OVER (ORDER BY id_cliente),
            id_cliente,
            nombre_cliente
        FROM (SELECT DISTINCT id_cliente, nombre_cliente FROM staging.stg_creditos) t
    """)
    print(f"[INIT] dim_cliente: {cur.rowcount} filas")

    # dim_tiempo
    cur.execute("""
        INSERT INTO marts.dim_tiempo
        SELECT
            CAST(to_char(fecha_originacion, 'YYYYMMDD') AS INTEGER),
            fecha_originacion,
            EXTRACT(YEAR FROM fecha_originacion)::INTEGER,
            EXTRACT(MONTH FROM fecha_originacion)::INTEGER,
            CASE EXTRACT(MONTH FROM fecha_originacion)::INTEGER
                WHEN 1 THEN 'Enero'   WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo'
                WHEN 4 THEN 'Abril'   WHEN 5 THEN 'Mayo'    WHEN 6 THEN 'Junio'
                WHEN 7 THEN 'Julio'   WHEN 8 THEN 'Agosto'  WHEN 9 THEN 'Septiembre'
                WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre'
            END,
            EXTRACT(DAY FROM fecha_originacion)::INTEGER,
            EXTRACT(DOW FROM fecha_originacion)::INTEGER,
            CASE EXTRACT(DOW FROM fecha_originacion)::INTEGER
                WHEN 0 THEN 'Domingo' WHEN 1 THEN 'Lunes'   WHEN 2 THEN 'Martes'
                WHEN 3 THEN 'Miercoles' WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes'
                WHEN 6 THEN 'Sabado'
            END,
            CASE
                WHEN EXTRACT(MONTH FROM fecha_originacion)::INTEGER IN (1,2,3) THEN 1
                WHEN EXTRACT(MONTH FROM fecha_originacion)::INTEGER IN (4,5,6) THEN 2
                WHEN EXTRACT(MONTH FROM fecha_originacion)::INTEGER IN (7,8,9) THEN 3
                ELSE 4
            END,
            EXTRACT(DOW FROM fecha_originacion)::INTEGER IN (0,6)
        FROM (SELECT DISTINCT fecha_originacion FROM staging.stg_creditos) t
        ORDER BY fecha_originacion
    """)
    print(f"[INIT] dim_tiempo: {cur.rowcount} filas")

    # dim_industria
    cur.execute("""
        INSERT INTO marts.dim_industria (industria_id, nombre_industria)
        SELECT
            ROW_NUMBER() OVER (ORDER BY industria),
            industria
        FROM (SELECT DISTINCT industria AS industria FROM staging.stg_creditos) t
    """)
    print(f"[INIT] dim_industria: {cur.rowcount} filas")

    cur.close()


def construir_fact(conn):
    """Construye fact_originaciones haciendo JOIN a las dimensiones."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO marts.fact_originaciones
        SELECT
            ROW_NUMBER() OVER (ORDER BY stg.id_credito),
            stg.id_credito,
            dc.cliente_id,
            dt.tiempo_id,
            di.industria_id,
            stg.monto,
            stg.plazo_meses,
            stg.canal,
            stg.estatus_primer_pago
        FROM staging.stg_creditos AS stg
        LEFT JOIN marts.dim_cliente   AS dc ON stg.id_cliente = dc.id_cliente
        LEFT JOIN marts.dim_tiempo    AS dt ON stg.fecha_originacion = dt.fecha_originacion
        LEFT JOIN marts.dim_industria AS di ON stg.industria = di.nombre_industria
    """)
    count = cur.rowcount
    cur.close()
    print(f"[INIT] fact_originaciones: {count} filas")


# ── Main ─────────────────────────────────────────────────────────────────────


def verificar_cargas(conn):
    """Verifica que todas las tablas tengan datos."""
    cur = conn.cursor()
    tablas = [
        ("raw", "raw_creditos"),
        ("staging", "stg_creditos"),
        ("marts", "dim_cliente"),
        ("marts", "dim_tiempo"),
        ("marts", "dim_industria"),
        ("marts", "fact_originaciones"),
    ]
    print("[ETL] Verificando filas cargadas:")
    for schema, tabla in tablas:
        try:
            cur.execute(f'SELECT COUNT(*) FROM {schema}."{tabla}"')
            count = cur.fetchone()[0]
            print(f"[ETL]   {schema}.{tabla:<30s} = {count:>6,} filas")
        except Exception as e:
            print(f"[ETL]   {schema}.{tabla:<30s} = ERROR: {e}")
    cur.close()


def main():
    # 0. Conectar con reintentos
    print("[ETL] Conectando a PostgreSQL...")
    conn = conectar()

    try:
        # 0.5 Esperar a que initdb cree las tablas
        print("[ETL] Esperando a que las tablas existan...")
        esperar_tablas(conn)

        # 0.6 Crear funciones de casting seguro
        print("[ETL] Creando funciones try_cast_*...")
        crear_funciones_seguras(conn)

        # 0.7 Limpiar datos previos
        print("[ETL] Paso 0/4: Limpiando datos previos...")
        truncar_todo(conn)

        # 1. Cargar CSV
        print("[ETL] Paso 1/4: Cargando CSV a raw...")
        cargar_raw(conn)

        # 2. Staging
        print("[ETL] Paso 2/4: Transformando staging...")
        transformar_staging(conn)

        # 3. Dimensiones
        print("[ETL] Paso 3/4: Construyendo dimensiones...")
        construir_dimensiones(conn)

        # 4. Fact
        print("[ETL] Paso 4/4: Construyendo fact table...")
        construir_fact(conn)

        # 5. Verificar
        verificar_cargas(conn)

        print("[ETL] Modelo estrella construido exitosamente.")
    except Exception as e:
        print(f"[ETL] ERROR FATAL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
