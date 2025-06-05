# NiceGrow

Este repositorio contiene el proyecto SandyBot. Para ejecutarlo se requiere
instalar las dependencias listadas en `requirements.txt`. Se recomienda usar
la versión `openai>=1.0.0` para garantizar compatibilidad con la nueva
API utilizada en `sandybot`.

## Plantilla de informes de repetitividad

El documento base para generar los reportes de repetitividad se indica
mediante la variable de entorno `PLANTILLA_PATH`. Si no se define, el
código toma la ruta por defecto `C:\Metrotel\Sandy\plantilla_informe.docx`
tal como se especifica en `config.py`.
