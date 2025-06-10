# NiceGrow

Este repositorio contiene el proyecto SandyBot. Para ejecutarlo se requiere
instalar las dependencias listadas en `requirements.txt`. Se recomienda usar
la versión `openai>=1.0.0` para garantizar compatibilidad con la nueva
API utilizada en `sandybot`.
Desde esta versión el bot también acepta mensajes de voz, los descarga y
transcribe automáticamente utilizando la API de OpenAI.

## Variables de entorno

El comportamiento de SandyBot se ajusta mediante varias variables de entorno:

- `PLANTILLA_PATH`: ruta de la plantilla para los informes de repetitividad. Si
  no se define, se usa `C:\Metrotel\Sandy\plantilla_informe.docx`.
- `GPT_MODEL`: modelo de OpenAI a emplear. Por defecto se aplica `gpt-4`.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`: datos para el servidor
  de correo saliente.
- `SMTP_USE_TLS`: indica si se inicia TLS al conectarse (por defecto `true`).
- También se aceptan `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER` y
  `EMAIL_PASSWORD` para mantener compatibilidad con versiones antiguas.

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
SMTP_PASSWORD=tu_contraseña_de_app
EMAIL_FROM=tu_correo@gmail.com
```

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

Al iniciar el bot, `init_db()` crea las tablas de forma automática y
ejecuta `ensure_servicio_columns()` para garantizar que la tabla
`servicios` incluya las columnas `ruta_tracking`, `trackings`, `camaras`,
`carrier` e `id_carrier`.

Las columnas `camaras` y `trackings` ahora utilizan el tipo
`JSONB`, por lo que almacenan listas o diccionarios de manera
nativa. Ya no es necesario convertir los datos a texto con
`json.dumps` ni decodificarlos al leerlos.

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


## Licencia

Este proyecto se publica bajo la licencia [MIT](LICENSE).

