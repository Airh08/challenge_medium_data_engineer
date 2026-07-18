-- ============================================================================
-- 01_create_tables.sql
-- DDL del modelo estrella para PostgreSQL
-- Se ejecuta automáticamente al iniciar el contenedor PostgreSQL.
-- ============================================================================

-- ── Esquema raw (datos crudos desde CSV) ───────────────────────────────────

DROP TABLE IF EXISTS raw.raw_creditos CASCADE;
DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

-- ── Funciones de casting seguro (equivalente a TRY_CAST de DuckDB) ─────────
-- PostgreSQL lanza error con CAST inválido. Estas funciones devuelven NULL
-- en lugar de abortar, permitiendo filtrar los nulos downstream.

CREATE OR REPLACE FUNCTION try_cast_date(txt TEXT) RETURNS DATE AS $$
BEGIN
    RETURN CAST(txt AS DATE);
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION try_cast_double(txt TEXT) RETURNS DOUBLE PRECISION AS $$
BEGIN
    RETURN CAST(txt AS DOUBLE PRECISION);
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION try_cast_integer(txt TEXT) RETURNS INTEGER AS $$
BEGIN
    RETURN CAST(txt AS INTEGER);
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ── Tabla raw ──────────────────────────────────────────────────────────────

CREATE TABLE raw.raw_creditos (
    id_credito          TEXT,
    fecha_originacion   TEXT,
    id_cliente          TEXT,
    nombre_cliente      TEXT,
    industria           TEXT,
    monto               TEXT,
    plazo_meses         TEXT,
    canal               TEXT,
    estatus_primer_pago TEXT
);

-- ── Esquema staging ────────────────────────────────────────────────────────

DROP TABLE IF EXISTS staging.stg_creditos CASCADE;
DROP SCHEMA IF EXISTS staging CASCADE;
CREATE SCHEMA staging;

CREATE TABLE staging.stg_creditos (
    id_credito          TEXT PRIMARY KEY,
    fecha_originacion   DATE,
    id_cliente          TEXT,
    nombre_cliente      TEXT,
    industria           TEXT,
    monto               DOUBLE PRECISION,
    plazo_meses         INTEGER,
    canal               TEXT,
    estatus_primer_pago TEXT
);

-- ── Esquema marts: modelo estrella ─────────────────────────────────────────

DROP TABLE IF EXISTS marts.fact_originaciones CASCADE;
DROP TABLE IF EXISTS marts.dim_industria CASCADE;
DROP TABLE IF EXISTS marts.dim_tiempo CASCADE;
DROP TABLE IF EXISTS marts.dim_cliente CASCADE;
DROP SCHEMA IF EXISTS marts CASCADE;
CREATE SCHEMA marts;

-- Dimensión: Cliente
CREATE TABLE marts.dim_cliente (
    cliente_id      INTEGER PRIMARY KEY,
    id_cliente      TEXT NOT NULL,
    nombre_cliente  TEXT
);

-- Dimensión: Tiempo
CREATE TABLE marts.dim_tiempo (
    tiempo_id           INTEGER PRIMARY KEY,
    fecha_originacion   DATE NOT NULL,
    anio                INTEGER,
    mes                 INTEGER,
    nombre_mes          TEXT,
    dia                 INTEGER,
    dia_semana          INTEGER,
    nombre_dia_semana   TEXT,
    trimestre           INTEGER,
    es_fin_de_semana    BOOLEAN
);

-- Dimensión: Industria
CREATE TABLE marts.dim_industria (
    industria_id        INTEGER PRIMARY KEY,
    nombre_industria    TEXT NOT NULL
);

-- Hechos: Originaciones
CREATE TABLE marts.fact_originaciones (
    originacion_id      INTEGER PRIMARY KEY,
    id_credito          TEXT NOT NULL,
    cliente_id          INTEGER REFERENCES marts.dim_cliente(cliente_id),
    tiempo_id           INTEGER REFERENCES marts.dim_tiempo(tiempo_id),
    industria_id        INTEGER REFERENCES marts.dim_industria(industria_id),
    monto               DOUBLE PRECISION,
    plazo_meses         INTEGER,
    canal               TEXT,
    estatus_primer_pago TEXT
);

-- ── Índices para queries de KPIs ───────────────────────────────────────────

CREATE INDEX idx_fact_cliente   ON marts.fact_originaciones(cliente_id);
CREATE INDEX idx_fact_tiempo    ON marts.fact_originaciones(tiempo_id);
CREATE INDEX idx_fact_industria ON marts.fact_originaciones(industria_id);
CREATE INDEX idx_fact_canal     ON marts.fact_originaciones(canal);
CREATE INDEX idx_fact_monto     ON marts.fact_originaciones(monto);
