# NiceGrow

Este repositorio contiene el proyecto SandyBot. Para ejecutarlo se requiere
instalar las dependencias listadas en `Sandy bot/requirements.txt`. Se recomienda usar
la versión `openai>=1.0.0` para garantizar compatibilidad con la nueva
API utilizada en `sandybot`.
Desde esta versión el bot también acepta mensajes de voz, los descarga y
transcribe automáticamente utilizando la API de OpenAI.

## Variables de entorno

El comportamiento de SandyBot se ajusta mediante varias variables de entorno:

- `PLANTILLA_PATH`: ruta de la plantilla para los informes de repetitividad. Si
  no se define, se usa `C:\Metrotel\Sandy\plantilla_informe.docx`.
- `SIGNATURE_PATH`: ruta a la firma opcional que se agregará en los correos.
- `GPT_MODEL`: modelo de OpenAI a emplear. Por defecto se aplica `gpt-4`.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`: datos para el servidor
  de correo saliente.
- `SMTP_USE_TLS`: controla si se inicia TLS. Si se define como `false` o se usa
  el puerto 465 se emplea `SMTP_SSL`; en caso contrario se ejecuta `starttls()`.
- También se aceptan `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER` y
  `EMAIL_PASSWORD` para mantener compatibilidad con versiones antiguas.
- `PYTHONPATH`: `main.py` agrega de forma automática la carpeta `Sandy bot`.
  `setup_env.sh` exporta la misma ruta para facilitar las pruebas y la
  ejecución desde otros scripts.

### Envío de correos

Para adjuntar archivos por email se utilizan las siguientes variables opcionales:

- `SMTP_HOST` y `SMTP_PORT`: servidor y puerto del servicio SMTP.
- `SMTP_USER` y `SMTP_PASSWORD`: credenciales si el servidor las requiere.
- `EMAIL_FROM`: dirección remitente utilizada en los mensajes.

Si vas a usar Gmail en desarrollo, activá la verificación en dos pasos y generá
una **contraseña de aplicación**. Definí las variables así:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_correo@gmail.com
SMTP_PASSWORD=tu_contrasena_de_app  # sin espacios
EMAIL_FROM=tu_correo@gmail.com
```
Nota: si copiás la contraseña de aplicación de Gmail, asegurate de quitar los espacios que se muestran por legibilidad.

## Plantilla de informes de repetitividad

El documento base para generar los reportes de repetitividad se indica
mediante la variable de entorno `PLANTILLA_PATH`. Si no se define, el
código toma la ruta por defecto `C:\Metrotel\Sandy\plantilla_informe.docx`
tal como se especifica en `config.py`.

## Base de datos

Se incluyen dos modelos principales:

1. **Conversacion**: almacena el historial de mensajes del bot.
2. **Servicio**: registra nombre, cliente, carrier e ID carrier.
   También guarda la ruta del informe de comparación, los trackings
   asociados y las cámaras involucradas en cada servicio.

3. **Cliente**: guarda el nombre de cada cliente y los correos
   utilizados para enviar notificaciones.
4. **TareaProgramada**: representa las ventanas de mantenimiento que
   informan los carriers. Registra `fecha_inicio`, `fecha_fin`,
   `tipo_tarea`, `tiempo_afectacion` y una breve `descripcion`.
5. **TareaServicio**: vincula cada tarea programada con los servicios
   afectados mediante sus IDs.

Antes de crear la instancia del bot se ejecuta `init_db()` desde
`main.py`. Esta función crea las tablas y ejecuta
`ensure_servicio_columns()` para garantizar que la tabla `servicios`
incluya las columnas `ruta_tracking`, `trackings`, `camaras`, `carrier` e
`id_carrier`.

Para aprovechar las búsquedas acentuadas se utilizan las extensiones
`unaccent` y `pg_trgm`.  El usuario configurado en la base debe tener
permisos para instalarlas o bien se deben crear manualmente con una
cuenta administradora antes de iniciar el bot.

Las columnas `camaras` y `trackings` ahora utilizan el tipo
`JSONB`, por lo que almacenan listas o diccionarios de manera
nativa. Ya no es necesario convertir los datos a texto con
`json.dumps` ni decodificarlos al leerlos.

Si durante el envío de cámaras ocurre un error de conexión con la base,
Sandy mostrará el mensaje:
"No pude conectarme a la base de datos. Verificá la configuración.".

### Registrar tareas programadas

Para crear una tarea desde el bot se utiliza el comando:
`/registrar_tarea <cliente> <inicio> <fin> <tipo> <id1,id2>`.
El sistema guarda la ventana de mantenimiento en `tareas_programadas`
y vincula los servicios indicados en `tareas_servicio`. Los datos
almacenados incluyen inicio, fin, tipo de tarea, tiempo de afectación
y una descripción opcional.

```python
from datetime import datetime
from sandybot.database import crear_tarea_programada

tarea = crear_tarea_programada(
    datetime(2024, 1, 2, 8),
    datetime(2024, 1, 2, 10),
    "Mantenimiento",
    [42],
    tiempo_afectacion="2h",
    descripcion="Pruebas de red",
)
```

## Carga de tracking

Utilizá el comando `/cargar_tracking` y enviá el archivo `.txt`.
El bot detectará el ID del servicio en el nombre (por ejemplo `FO_1234_tramo.txt`)
y mostrará dos botones para **Procesar tracking** o **Modificar ID**.
También se acepta la confirmación escribiendo "sí" o "si".
Si el ID no existe en la base de datos, Sandy creará el servicio automáticamente
al guardar el tracking.
Para recuperar un archivo existente podés usar `/descargar_tracking` y
especificar el número de servicio.

## Identificador de servicio Carrier

Desde el menú principal es posible seleccionar **Identificador de servicio Carrier**.
Esta opción recibe un Excel con las columnas "ID Servicio" e "ID Carrier".
El bot completa los valores faltantes consultando la base de datos y devuelve el archivo actualizado.
Luego de enviar el Excel, cada fila se registra en la tabla `servicios`,
actualizando el `id_carrier` si el servicio existe o creando una entrada nueva
en caso contrario.

## Analizador de incidencias


Esta función genera un resumen de las fallas registradas en reportes de campo. Ahora acepta archivos `.docx` y `.doc`, incluso varios adjuntos al mismo tiempo. Para procesar documentos `.doc` se debe instalar la biblioteca `textract`.


```bash
pip install textract
```

Entre los adjuntos se puede incluir un archivo de contexto o correos electrónicos. En el futuro se usará una API para obtener las incidencias de manera automática.

Para iniciar el análisis, seleccioná **Analizador de incidencias** en el menú principal o ejecutá `/analizar_incidencias`. Luego enviá el documento `.docx` y el bot responderá con los hallazgos. Además, recibirás un nuevo `.docx` con la cronología de eventos extraídos.

### Habilitar lectura de `.doc`

Si necesitás procesar documentos con extensión `.doc`, instalá el paquete opcional `textract`:

```bash
pip install textract
```


También podés incluirlo al instalar todas las dependencias:

```bash
pip install -r requirements.txt
```

## Enviar Excel por correo

Para mandar un reporte por email se usa la función `enviar_excel_por_correo()`
de `sandybot.email_utils`. No requiere instalar paquetes adicionales porque
aprovecha `smtplib` y `email` de la biblioteca estándar.

```python
from sandybot.email_utils import enviar_excel_por_correo

exito = enviar_excel_por_correo(
    "destino@example.com",
    "reporte.xlsx",
    asunto="Reporte semanal",
    cuerpo="Adjunto el archivo solicitado."
)
if exito:
    print("Correo enviado correctamente")
```

Asegurate de definir `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` y `SMTP_PASSWORD`
en tu `.env` para que el envío funcione. Si aún usás las variables
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER` o `EMAIL_PASSWORD`, SandyBot
las tomará automáticamente.


## Errores por variables de entorno faltantes

Al iniciar el bot, `config.py` valida que todas las variables de entorno
necesarias estén definidas. Si alguna falta, se genera un mensaje como:


```
⚠️ No se encontraron las siguientes variables de entorno requeridas: VAR1, VAR2.
Verificá tu archivo .env o las variables del sistema.
```

Este texto se registra con `logging.error` y luego se lanza una excepción
`ValueError` con el mismo contenido. Revisá el archivo `.env` o la configuración
del sistema para corregir el problema.

## Pruebas automatizadas

Para validar el funcionamiento del proyecto se incluye una suite de pruebas basada en `pytest`.
Es necesario contar con las bibliotecas `openpyxl`, `python-docx` y `pandas` para que todas las
pruebas puedan ejecutarse correctamente.

Antes de ejecutar `pytest` es recomendable preparar el entorno con `setup_env.sh`.
Este script crea el virtualenv en `.venv` y realiza la instalación de
`Sandy bot/requirements.txt` automáticamente. Además exporta la ruta
`Sandy bot` en `PYTHONPATH` para que las importaciones funcionen sin ajustes
manuales.

```bash
./setup_env.sh
pytest
```

Algunas pruebas relacionadas con la base de datos se omiten de forma automática si `SQLAlchemy`
no está presente en el entorno.


## Licencia

Este proyecto se publica bajo la licencia [MIT](LICENSE).

