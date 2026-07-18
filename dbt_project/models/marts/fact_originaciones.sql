{# -- fact_originaciones.sql ----------------------------------------------------
   Tabla de hechos: originaciones de crédito.
   Referencia las dimensiones cliente, tiempo e industria mediante surrogate keys.
#}

SELECT
    ROW_NUMBER() OVER (ORDER BY stg.id_credito) AS originacion_id,
    stg.id_credito,
    dim_cl.cliente_id,
    dim_ti.tiempo_id,
    dim_in.industria_id,
    stg.monto,
    stg.plazo_meses,
    stg.canal,
    stg.estatus_primer_pago
FROM {{ ref('stg_creditos') }} AS stg
LEFT JOIN {{ ref('dim_cliente') }}   AS dim_cl
    ON stg.id_cliente = dim_cl.id_cliente
LEFT JOIN {{ ref('dim_tiempo') }}    AS dim_ti
    ON stg.fecha_originacion = dim_ti.fecha_originacion
LEFT JOIN {{ ref('dim_industria') }} AS dim_in
    ON stg.industria = dim_in.nombre_industria
