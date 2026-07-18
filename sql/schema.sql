-- ============================================================================
-- schema.sql
-- DDL del modelo estrella para originaciones de créditos PYME
-- ============================================================================
-- Este archivo documenta la estructura del modelo dimensional.
-- Las tablas son materializadas por dbt (dbt_runner.py) sobre DuckDB.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Esquema: staging (capa intermedia de limpieza)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.stg_creditos (
    id_credito          VARCHAR PRIMARY KEY,
    fecha_originacion   DATE,
    id_cliente          VARCHAR,
    nombre_cliente      VARCHAR,
    industria           VARCHAR,
    monto               DOUBLE,
    plazo_meses         INTEGER,
    canal               VARCHAR,
    estatus_primer_pago VARCHAR
);

-- ----------------------------------------------------------------------------
-- Esquema: marts (modelo estrella)
-- ----------------------------------------------------------------------------

-- Dimensión: Cliente
CREATE TABLE IF NOT EXISTS marts.dim_cliente (
    cliente_id      INTEGER PRIMARY KEY,   -- Surrogate key
    id_cliente      VARCHAR NOT NULL,       -- Business key
    nombre_cliente  VARCHAR
);

-- Dimensión: Tiempo
CREATE TABLE IF NOT EXISTS marts.dim_tiempo (
    tiempo_id           INTEGER PRIMARY KEY,  -- YYYYMMDD
    fecha_originacion   DATE NOT NULL,
    anio                INTEGER,
    mes                 INTEGER,
    nombre_mes          VARCHAR,
    dia                 INTEGER,
    dia_semana          INTEGER,
    nombre_dia_semana   VARCHAR,
    trimestre           INTEGER,
    es_fin_de_semana    BOOLEAN
);

-- Dimensión: Industria
CREATE TABLE IF NOT EXISTS marts.dim_industria (
    industria_id        INTEGER PRIMARY KEY,   -- Surrogate key
    nombre_industria    VARCHAR NOT NULL        -- Business key
);

-- Hechos: Originaciones
CREATE TABLE IF NOT EXISTS marts.fact_originaciones (
    originacion_id      INTEGER PRIMARY KEY,   -- Surrogate key
    id_credito          VARCHAR NOT NULL,       -- Business key (CDC-ready)
    cliente_id          INTEGER,                -- FK → dim_cliente
    tiempo_id           INTEGER,                -- FK → dim_tiempo
    industria_id        INTEGER,                -- FK → dim_industria
    monto               DOUBLE,
    plazo_meses         INTEGER,
    canal               VARCHAR,
    estatus_primer_pago VARCHAR,
    FOREIGN KEY (cliente_id)   REFERENCES marts.dim_cliente(cliente_id),
    FOREIGN KEY (tiempo_id)    REFERENCES marts.dim_tiempo(tiempo_id),
    FOREIGN KEY (industria_id) REFERENCES marts.dim_industria(industria_id)
);

-- ----------------------------------------------------------------------------
-- Índices sugeridos para optimizar las queries de KPIs
-- ----------------------------------------------------------------------------
-- CREATE INDEX idx_fact_cliente   ON marts.fact_originaciones(cliente_id);
-- CREATE INDEX idx_fact_tiempo    ON marts.fact_originaciones(tiempo_id);
-- CREATE INDEX idx_fact_industria ON marts.fact_originaciones(industria_id);
