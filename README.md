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

## Base de datos

Se incluyen dos modelos principales:

1. **Conversacion**: almacena el historial de mensajes del bot.
2. **Servicio**: registra nombre, cliente y los trackings asociados.
   También guarda la ruta del informe de comparación y las cámaras
   involucradas en cada servicio.

## Carga de tracking

Utilizá el comando `/cargar_tracking` y simplemente enviá el archivo `.txt`.
El bot detectará el ID del servicio en el nombre (por ejemplo `FO_1234_tramo.txt`)
y preguntará si deseás asociarlo. Podés confirmar respondiendo "sí" o
escribir otro ID para reemplazarlo.

