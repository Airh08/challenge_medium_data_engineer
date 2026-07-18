{# -- dim_cliente.sql -----------------------------------------------------------
   Dimensión de clientes: un registro por cada id_cliente único.
   Surrogate key: cliente_id (generada con ROW_NUMBER).
#}

WITH clientes_unicos AS (
    SELECT DISTINCT
        id_cliente,
        nombre_cliente
    FROM {{ ref('stg_creditos') }}
)

SELECT
    ROW_NUMBER() OVER (ORDER BY id_cliente) AS cliente_id,
    id_cliente,
    nombre_cliente
FROM clientes_unicos
