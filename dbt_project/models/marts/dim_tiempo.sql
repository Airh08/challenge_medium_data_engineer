{# -- dim_tiempo.sql ------------------------------------------------------------
   Dimensión de tiempo: un registro por cada fecha de originación distinta.
   Surrogate key: tiempo_id (formato YYYYMMDD como INTEGER).
#}

WITH fechas_unicas AS (
    SELECT DISTINCT fecha_originacion
    FROM {{ ref('stg_creditos') }}
)

SELECT
    CAST(strftime(fecha_originacion, '%Y%m%d') AS INTEGER) AS tiempo_id,
    fecha_originacion,
    CAST(strftime(fecha_originacion, '%Y') AS INTEGER)    AS anio,
    CAST(strftime(fecha_originacion, '%m') AS INTEGER)    AS mes,
    CASE strftime(fecha_originacion, '%m')
        WHEN '01' THEN 'Enero'
        WHEN '02' THEN 'Febrero'
        WHEN '03' THEN 'Marzo'
        WHEN '04' THEN 'Abril'
        WHEN '05' THEN 'Mayo'
        WHEN '06' THEN 'Junio'
        WHEN '07' THEN 'Julio'
        WHEN '08' THEN 'Agosto'
        WHEN '09' THEN 'Septiembre'
        WHEN '10' THEN 'Octubre'
        WHEN '11' THEN 'Noviembre'
        WHEN '12' THEN 'Diciembre'
    END                                                   AS nombre_mes,
    CAST(strftime(fecha_originacion, '%d') AS INTEGER)    AS dia,
    CAST(strftime(fecha_originacion, '%w') AS INTEGER)    AS dia_semana,
    CASE strftime(fecha_originacion, '%w')
        WHEN '0' THEN 'Domingo'
        WHEN '1' THEN 'Lunes'
        WHEN '2' THEN 'Martes'
        WHEN '3' THEN 'Miercoles'
        WHEN '4' THEN 'Jueves'
        WHEN '5' THEN 'Viernes'
        WHEN '6' THEN 'Sabado'
    END                                                   AS nombre_dia_semana,
    CASE
        WHEN CAST(strftime(fecha_originacion, '%m') AS INTEGER) IN (1, 2, 3)
        THEN 1
        WHEN CAST(strftime(fecha_originacion, '%m') AS INTEGER) IN (4, 5, 6)
        THEN 2
        WHEN CAST(strftime(fecha_originacion, '%m') AS INTEGER) IN (7, 8, 9)
        THEN 3
        ELSE 4
    END                                                   AS trimestre,
    CASE
        WHEN strftime(fecha_originacion, '%w') IN ('0', '6') THEN TRUE
        ELSE FALSE
    END                                                   AS es_fin_de_semana
FROM fechas_unicas
ORDER BY fecha_originacion
