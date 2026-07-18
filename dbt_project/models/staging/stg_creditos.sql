{# -- staging: stg_creditos.sql -------------------------------------------------
   Lee los datos crudos desde raw_creditos en DuckDB, limpia tipados,
   filtra registros con problemas de calidad y deduplica por id_credito.
   Usa TRY_CAST para manejar defensivamente cualquier valor inválido residual.
#}

-- 1. Filtrar filas con valores vacíos antes de cualquier conversión
WITH filtered AS (
    SELECT *
    FROM {{ source('raw', 'raw_creditos') }}
    WHERE id_credito IS NOT NULL
      AND id_credito != ''
      AND fecha_originacion IS NOT NULL
      AND fecha_originacion != ''
      AND monto IS NOT NULL
),

-- 2. Convertir tipos (TRY_CAST evita errores fatales)
source AS (
    SELECT
        id_credito,
        TRY_CAST(fecha_originacion AS DATE) AS fecha_originacion,
        id_cliente,
        nombre_cliente,
        industria,
        TRY_CAST(monto AS DOUBLE)          AS monto,
        TRY_CAST(plazo_meses AS INTEGER)   AS plazo_meses,
        canal,
        estatus_primer_pago
    FROM filtered
),

-- 3. Eliminar filas donde el cast falló (esquema en U: nulls post-cast)
cast_ok AS (
    SELECT *
    FROM source
    WHERE fecha_originacion IS NOT NULL
      AND monto IS NOT NULL
),

-- 4. Validar montos en rango: $1,000 – $5,000,000 MXN
montos_validos AS (
    SELECT *
    FROM cast_ok
    WHERE monto >= 1000 AND monto <= 5000000
),

-- 5. Deduplicar por id_credito (conservar el primero por fecha)
deduplicados AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY id_credito
            ORDER BY fecha_originacion
        ) AS rn
    FROM montos_validos
)

SELECT
    id_credito,
    fecha_originacion,
    id_cliente,
    nombre_cliente,
    industria,
    monto,
    plazo_meses,
    canal,
    estatus_primer_pago
FROM deduplicados
WHERE rn = 1
