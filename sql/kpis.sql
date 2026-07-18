-- ============================================================================
-- kpis.sql
-- ============================================================================
-- Queries analíticas de KPIs contra el modelo estrella (DuckDB).
--
-- Convenciones:
--   - Todos los KPIs se ejecutan sobre marts.fact_originaciones (f) y sus
--     dimensiones asociadas (dim_cliente, dim_tiempo, dim_industria).
--   - Se asume que los datos ya pasaron por el pipeline de calidad.
-- ============================================================================

-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI 1: TOTAL ORIGINADO EN EL MES
-- Suma de los montos de todos los créditos originados en el período.
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    COUNT(*)                AS total_creditos,
    SUM(f.monto)            AS monto_total_originado,
    ROUND(AVG(f.monto), 2)  AS ticket_promedio
FROM marts.fact_originaciones AS f;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI 2: TOP 5 INDUSTRIAS POR CRÉDITOS Y MONTO
-- Conteo y monto total por sector, los cinco principales.
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    di.nombre_industria,
    COUNT(*)                AS num_creditos,
    SUM(f.monto)            AS monto_total,
    ROUND(AVG(f.monto), 2)  AS ticket_promedio
FROM marts.fact_originaciones AS f
JOIN marts.dim_industria     AS di ON f.industria_id = di.industria_id
GROUP BY di.nombre_industria
ORDER BY monto_total DESC
LIMIT 5;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI 3: TICKET PROMEDIO POR SEGMENTO DE CLIENTE
-- Clasifica los créditos por rango de monto usando CASE WHEN.
-- Segmentos: Micro (< $50K), Pequeño ($50K-$250K), Mediano ($250K-$1M),
--            Grande ($1M-$5M)
-- ═══════════════════════════════════════════════════════════════════════════════

WITH creditos_con_segmento AS (
    SELECT
        f.id_credito,
        f.monto,
        CASE
            WHEN f.monto < 50000                      THEN 'Micro'
            WHEN f.monto >= 50000 AND f.monto < 250000  THEN 'Pequeno'
            WHEN f.monto >= 250000 AND f.monto < 1000000 THEN 'Mediano'
            WHEN f.monto >= 1000000                      THEN 'Grande'
        END AS segmento
    FROM marts.fact_originaciones AS f
)

SELECT
    segmento,
    COUNT(*)                AS num_creditos,
    SUM(monto)              AS monto_total,
    ROUND(AVG(monto), 2)    AS ticket_promedio,
    ROUND(MIN(monto), 2)    AS ticket_minimo,
    ROUND(MAX(monto), 2)    AS ticket_maximo
FROM creditos_con_segmento
GROUP BY segmento
ORDER BY ticket_promedio;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI 4: % DE PRIMER PAGO A TIEMPO vs. TARDÍO
-- Proporción de clientes que pagaron en fecha vs. con mora.
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    COUNT(*)                                                            AS total_creditos,
    SUM(CASE WHEN f.estatus_primer_pago = 'A Tiempo' THEN 1 ELSE 0 END) AS pagos_a_tiempo,
    SUM(CASE WHEN f.estatus_primer_pago = 'Tardío'   THEN 1 ELSE 0 END) AS pagos_tardios,
    ROUND(
        SUM(CASE WHEN f.estatus_primer_pago = 'A Tiempo' THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 1
    )                                                                   AS pct_a_tiempo,
    ROUND(
        SUM(CASE WHEN f.estatus_primer_pago = 'Tardío' THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 1
    )                                                                   AS pct_tardio
FROM marts.fact_originaciones AS f;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI 5: ÍNDICE DE MORA POR INDUSTRIA
-- ¿Qué industrias tienen más del 20% de sus créditos con primer pago tardío?
-- Usa GROUP BY + HAVING para filtrar industrias con alta morosidad.
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    di.nombre_industria,
    COUNT(*)                                                              AS total_creditos,
    SUM(CASE WHEN f.estatus_primer_pago = 'Tardío' THEN 1 ELSE 0 END)    AS creditos_morosos,
    ROUND(
        SUM(CASE WHEN f.estatus_primer_pago = 'Tardío' THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 1
    )                                                                     AS indice_mora_pct
FROM marts.fact_originaciones AS f
JOIN marts.dim_industria     AS di ON f.industria_id = di.industria_id
GROUP BY di.nombre_industria
HAVING ROUND(
    SUM(CASE WHEN f.estatus_primer_pago = 'Tardío' THEN 1 ELSE 0 END)
    * 100.0 / COUNT(*), 1
) > 20.0
ORDER BY indice_mora_pct DESC;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI ADICIONAL: DISTRIBUCIÓN DE CRÉDITOS POR CANAL
-- Conteo, monto total y ticket promedio por canal de originación.
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    f.canal,
    COUNT(*)                AS num_creditos,
    SUM(f.monto)            AS monto_total,
    ROUND(AVG(f.monto), 2)  AS ticket_promedio,
    ROUND(
        COUNT(*) * 100.0 / (SELECT COUNT(*) FROM marts.fact_originaciones), 1
    )                       AS pct_del_total
FROM marts.fact_originaciones AS f
GROUP BY f.canal
ORDER BY monto_total DESC;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI ADICIONAL: PLAZO PROMEDIO POR INDUSTRIA
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    di.nombre_industria,
    COUNT(*)                  AS num_creditos,
    ROUND(AVG(f.plazo_meses), 1) AS plazo_promedio_meses,
    MIN(f.plazo_meses)        AS plazo_min,
    MAX(f.plazo_meses)        AS plazo_max
FROM marts.fact_originaciones AS f
JOIN marts.dim_industria     AS di ON f.industria_id = di.industria_id
GROUP BY di.nombre_industria
ORDER BY plazo_promedio_meses DESC;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI ADICIONAL: TICKET MÁXIMO Y MÍNIMO POR CANAL
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    f.canal,
    COUNT(*)                AS num_creditos,
    ROUND(MIN(f.monto), 2)  AS ticket_minimo,
    ROUND(MAX(f.monto), 2)  AS ticket_maximo,
    ROUND(AVG(f.monto), 2)  AS ticket_promedio
FROM marts.fact_originaciones AS f
GROUP BY f.canal
ORDER BY ticket_promedio DESC;


-- ═══════════════════════════════════════════════════════════════════════════════
-- KPI ADICIONAL: MEDIANA DEL CRÉDITO (GLOBAL Y POR INDUSTRIA)
-- DuckDB soporta PERCENTILE_CONT y MEDIAN nativamente.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Mediana global
SELECT
    'Global'                        AS ambito,
    COUNT(*)                        AS num_creditos,
    ROUND(MEDIAN(f.monto), 2)      AS mediana_monto,
    ROUND(AVG(f.monto), 2)         AS promedio_monto,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY f.monto), 2) AS p25,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY f.monto), 2) AS p75
FROM marts.fact_originaciones AS f

UNION ALL

-- Mediana por industria
SELECT
    di.nombre_industria             AS ambito,
    COUNT(*)                        AS num_creditos,
    ROUND(MEDIAN(f.monto), 2)      AS mediana_monto,
    ROUND(AVG(f.monto), 2)         AS promedio_monto,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY f.monto), 2) AS p25,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY f.monto), 2) AS p75
FROM marts.fact_originaciones AS f
JOIN marts.dim_industria     AS di ON f.industria_id = di.industria_id
GROUP BY di.nombre_industria
ORDER BY mediana_monto DESC;


-- ═══════════════════════════════════════════════════════════════════════════════
-- RESUMEN MENSUAL: ORIGINACIONES POR MES
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    COUNT(*)                AS num_creditos,
    SUM(f.monto)            AS monto_total,
    ROUND(AVG(f.monto), 2)  AS ticket_promedio,
    ROUND(
        SUM(CASE WHEN f.estatus_primer_pago = 'A Tiempo' THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 1
    )                       AS pct_pago_a_tiempo
FROM marts.fact_originaciones AS f
JOIN marts.dim_tiempo        AS dt ON f.tiempo_id = dt.tiempo_id
GROUP BY dt.anio, dt.mes, dt.nombre_mes
ORDER BY dt.anio, dt.mes;
