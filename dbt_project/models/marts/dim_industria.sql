{# -- dim_industria.sql ---------------------------------------------------------
   Dimensión de industrias: un registro por cada sector único.
   Surrogate key: industria_id.
#}

WITH industrias_unicas AS (
    SELECT DISTINCT industria AS nombre_industria
    FROM {{ ref('stg_creditos') }}
)

SELECT
    ROW_NUMBER() OVER (ORDER BY nombre_industria) AS industria_id,
    nombre_industria
FROM industrias_unicas
