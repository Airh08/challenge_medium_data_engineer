# challenge_medium_data_engineer

## Cómo usé la IA

Para el desarrollo de este challenge utilicé **Claude Code** conectado con el modelo **DeepSeek** como asistente de programación.

### Preparación

Antes de comenzar, convertí el documento PDF del challenge a formato **Markdown** utilizando ChatGPT por las siguientes razones:

1. Reducir el consumo de contexto y tokens durante el desarrollo.
2. Facilitar el análisis del documento y mejorar el razonamiento de la IA al trabajar con texto estructurado.

### Desarrollo

Posteriormente, proporcioné el archivo en formato Markdown a Claude Code y le solicité desarrollar cada apartado del challenge de forma incremental.

Para la generación de datos sintéticos, indiqué explícitamente que:

- Utilizara **Python** como lenguaje de programación.
- Empleara la librería **Faker** para generar los datos simulados.
- Mantuviera una estructura de proyecto organizada y fácil de mantener.

### Código generado y revisado

| Archivo | Código generado por IA | Modificaciones realizadas | Correcciones realizadas |
|---------|-------------------------|---------------------------|-------------------------|
| `scripts/generate_data.py` | Generación del script para crear el archivo `creditos_mes.csv` con datos sintéticos utilizando Faker. | Se modificó la ruta de salida del archivo CSV para adaptarla a la estructura del proyecto y se agregó un sistema de logging para registrar la ejecución. | Se corrigió el manejo de rutas de salida para garantizar la compatibilidad con la estructura del repositorio. |