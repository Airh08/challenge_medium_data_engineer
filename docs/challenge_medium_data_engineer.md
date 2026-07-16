# INGENIERO DE DATOS — NIVEL MEDIUM

## Challenge Técnico:
# Dashboard de Originación y Cobranza de Créditos

> **Evaluación técnica · Entorno financiero · Uso de IA permitido**

- ⏱ **Duración:** 3 – 5 horas
- 🛠 **Herramientas:** Claude Code / Cursor / Codex CLI
- 📁 **Entrega:** Repositorio Git

---

# Instrucciones para el candidato

Bienvenido a esta evaluación técnica. Lee todo el documento antes de comenzar. El objetivo no es que entregues algo perfecto, sino que podamos ver cómo piensas y cómo trabajas con las herramientas disponibles.

## Reglas generales

- Puedes usar inteligencia artificial libremente (Claude Code, Cursor, Codex CLI u otro agente).
- El uso de IA no te penaliza; queremos entender cómo la integras a tu proceso.
- Todo el trabajo debe estar en un repositorio Git público o privado con acceso compartido.
- Incluye un `README.md` que explique tu razonamiento, no solo el resultado.
- Los commits deben mostrar tu progreso iterativo, no solo el estado final.

---

# Registro de uso de IA (obligatorio)

Al finalizar el challenge, ejecuta el siguiente comando desde la carpeta del proyecto para generar tu reporte de Paxel:

```bash
cd ~/path/to/tu-repo && curl -fsSL https://paxel.ycombinator.com/upload.sh | bash
```

Además del reporte, incluye en el `README`:

- Link o JSON del reporte generado por Paxel.
- Sección **"Cómo usé la IA"**:
  - Qué te generó.
  - Qué modificaste.
  - Qué tuviste que corregir.
- Un ejemplo concreto de un prompt que enviaste y el fragmento de código que aceptaste o rechazaste.
- **Nota:** Si usas una herramienta distinta a Claude Code / Cursor / Codex, documenta tus prompts en un archivo `ai-log.md`.

---

# Estructura esperada del repositorio

```text
README.md          -> Supuestos, decisiones, modelo dimensional y propuesta cloud
generate_data.py   -> Script que genera los datos sintéticos
pipeline.py        -> Ingesta, validación y carga al modelo dimensional
schema.sql         -> DDL del modelo estrella
kpis.sql           -> Queries de los KPIs requeridos
```

---

# Contexto del negocio

Eres nuevo en el equipo de datos de una financiera que otorga créditos a PYMES.

El analista de riesgo te pide construir un pipeline sencillo que procese el archivo de originaciones del mes y genere un resumen de KPIs que pueda revisar antes de la junta del lunes.

Tienes un solo archivo fuente:

`creditos_mes.csv`

Contiene aproximadamente **5,000 registros** de créditos otorgados en el mes, incluyendo datos del cliente, monto, plazo, industria y estatus del primer pago.

Tú mismo generarás este archivo con datos sintéticos como primer paso del challenge.

---

# KPIs que debes entregar

| KPI | Detalle |
|------|---------|
| **Total originado en el mes** | Suma de montos de todos los créditos del período. |
| **Créditos por industria (Top 5)** | Conteo y monto total por sector, los cinco principales. |
| **Ticket promedio por segmento** | Monto promedio de crédito clasificado por segmento de cliente. |
| **% de primer pago a tiempo vs. tardío** | Proporción de clientes que pagaron en fecha vs. con mora. |

---

# Partes del challenge

## Parte 1 — Generación de datos sintéticos

### 1. Script de datos sintéticos

Crea `generate_data.py` que produzca `creditos_mes.csv` con al menos los siguientes campos:

- id_credito
- fecha_originacion
- id_cliente
- nombre_cliente
- industria
- monto
- plazo_meses
- canal
- estatus_primer_pago

Incluye intencionalmente algunos problemas de calidad:

- Valores nulos
- Montos negativos
- Fechas inválidas

---

## Parte 2 — Calidad de datos

### 2. Tres validaciones obligatorias

Implementa las siguientes validaciones:

- Detección de nulos en:
  - id_credito
  - monto
  - fecha_originacion
- Montos fuera de rango:
  - Mínimo: **$1,000 MXN**
  - Máximo: **$5,000,000 MXN**
- Duplicados por `id_credito`

### 3. Reporte de calidad

Genera un reporte que muestre:

- Cuántos registros pasaron.
- Cuántos registros fallaron.
- Cuántos fallaron por cada regla.

Puede ser:

- Un CSV
- Un reporte estructurado en consola

---

## Parte 3 — Modelado dimensional básico

### 4. Modelo estrella simplificado

Diseña en SQL:

- fact_originaciones
- dim_cliente
- dim_tiempo
- dim_industria

Incluye:

- DDL completo
- Diagrama del modelo en el README
  - ASCII
  - o imagen

### 5. Carga al modelo

Utiliza:

- SQLite
- o DuckDB

Carga los datos limpios al modelo dimensional y ejecuta las queries de KPIs **contra las tablas del modelo**, no directamente sobre el CSV.

---

## Parte 4 — SQL analítico

### 6. Queries de los cuatro KPIs

Como mínimo:

- Una query debe utilizar:
  - `GROUP BY`
  - `HAVING`
- Otra debe utilizar:
  - `CASE WHEN`

para categorizar segmentos.

### 7. Query adicional

Responder:

> **¿Qué industrias tienen más del 20% de sus créditos con primer pago tardío?**

Escribe la consulta SQL correspondiente.

---

## Parte 5 — Nube conceptual (sin código)

### 8. Propuesta en el README

En **10–15 líneas**, responde:

> ¿Cómo pasarías este pipeline local a producción en la nube?

Incluye qué servicio utilizarías para:

- Orquestación
- Almacenamiento
- Visualización de KPIs

No necesita ser exhaustivo, pero sí coherente y justificado.

---

# 📋 Criterios de evaluación

| Área | Qué se evalúa |
|------|---------------|
| Calidad de datos | Cobertura y claridad de las validaciones implementadas |
| SQL | Correctitud de las queries y uso apropiado de GROUP BY, HAVING y CASE WHEN |
| Modelado dimensional | Estructura del modelo estrella y justificación de decisiones |
| Pipeline | Claridad, orden y robustez del código Python |
| Nube conceptual | Coherencia y razonamiento de la propuesta |
| Uso de IA | Capacidad de evaluar, corregir y dirigir al agente con criterio propio |