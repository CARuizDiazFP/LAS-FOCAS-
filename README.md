# NiceGrow

Este repositorio contiene el proyecto SandyBot. Para ejecutarlo se requiere
instalar las dependencias listadas en `Sandy bot/requirements.txt`. Se recomienda usar
la versión `openai>=1.0.0` para garantizar compatibilidad con la nueva
API utilizada en `sandybot`. Es obligatorio instalar `extract-msg` para leer los
adjuntos `.msg` y opcionalmente `pywin32` en Windows o `docx2pdf` en otros sistemas.
Estas librerías permiten insertar la firma, generar un `.MSG` real desde Outlook y exportar informes a PDF. Desde esta versión el bot también acepta
mensajes de voz, los descarga y los transcribe automáticamente utilizando la API
de OpenAI.
Antes de lanzar `pytest` o iniciar el bot es imprescindible ejecutar
`./setup_env.sh` para crear el entorno virtual e instalar todas las dependencias.

## Variables de entorno

El comportamiento de SandyBot se ajusta mediante varias variables de entorno:

- `PLANTILLA_PATH`: ruta de la plantilla para los informes de repetitividad. Si

- `SLA_TEMPLATE_PATH`: ruta de la plantilla para el Informe de SLA. Si no se define, se usa `Sandy bot/templates/Template Informe SLA.docx`.

- `SIGNATURE_PATH`: ruta a la firma opcional que se agregará en los correos.
- `GPT_MODEL`: modelo de OpenAI a emplear. Por defecto se aplica `gpt-4`.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`: datos para el servidor
  de correo saliente.
- `SUPER_PASS`: contraseña que habilita el menú de desarrollador.
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
- `SIGNATURE_PATH`: archivo de firma que se adjunta al final de cada aviso.

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

Para la suite de pruebas se pueden definir variables mínimas en un `.env` o en la consola antes de ejecutar `pytest`:

```bash
export TELEGRAM_TOKEN=dummy
export OPENAI_API_KEY=dummy
export NOTION_TOKEN=dummy
export NOTION_DATABASE_ID=dummy
export DB_USER=postgres
export DB_PASSWORD=postgres
```

## Modo desarrollador

El bot cuenta con un menú oculto para consultas internas. Se habilita
enviando `/Supermenu <contraseña>` desde Telegram. La clave se toma de
`SUPER_PASS` y por omisión vale `Bio123`. Al validarla se muestran los
botones `/CDB_Servicios`, `/CDB_Reclamos` y `/CDB_Camaras`.

## Plantilla de informes de repetitividad

El documento base para generar los reportes de repetitividad se indica
mediante la variable de entorno `PLANTILLA_PATH`. Si no se define, el
código toma la ruta por defecto `C:\Metrotel\Sandy\plantilla_informe.docx`
tal como se especifica en `config.py`.
El título del documento se ajusta al mes actual en español y, si la plantilla
no cuenta con el estilo `Title`, se utiliza `Heading 1` como alternativa.
En el menú del bot existe un botón para reemplazar la plantilla de
repetitividad y otro que permite exportar el informe final a PDF.
Las plantillas de ejemplo se guardan en la carpeta `templates/` y cada versión
anterior se mueve automáticamente a `templates/Historicos` al presionar
**Actualizar plantilla**. De esta forma la nueva base queda disponible para los
próximos informes sin perder el historial.

## Plantilla del informe de SLA

Para los reportes de nivel de servicio se utiliza un archivo Word
configurable por `SLA_TEMPLATE_PATH`. Si la variable no está presente,
se recurre a `Sandy bot/templates/Template Informe SLA.docx`.
El sistema valida que la ruta indicada exista. En caso de no
encontrarla se registra el mensaje **"Plantilla de SLA no encontrada"**
y se lanza `ValueError`.

```env
# Ejemplo para personalizar la plantilla en otra ubicación
SLA_TEMPLATE_PATH=D:\Informes\MiPlantilla.docx
```

## Base de datos

Se incluyen dos modelos principales:

1. **Conversacion**: almacena el historial de mensajes del bot.
2. **Servicio**: registra nombre, cliente, carrier e ID carrier.
   También guarda la ruta del informe de comparación, los trackings
   asociados y las cámaras involucradas en cada servicio.

3. **Cliente**: guarda el nombre de cada cliente y los correos
   utilizados para enviar notificaciones.
4. **Carrier**: tabla con los carriers disponibles. Solo almacena `id` y
   `nombre`.
5. **TareaProgramada**: representa las ventanas de mantenimiento que
   informan los carriers. Registra `fecha_inicio`, `fecha_fin`,
   `tipo_tarea`, `tiempo_afectacion`, `descripcion` y `carrier_id`.
6. **TareaServicio**: vincula cada tarea programada con los servicios
   afectados mediante sus IDs.
7. **Reclamo**: almacena los tickets asociados a un servicio. Guarda
   número, fecha de inicio, fecha de cierre, tipo de solución y una
   descripción de la solución.
8. Las tablas `camaras` y `reclamos` cuentan con restricciones únicas que
   evitan registrar dos veces la misma cámara o número de reclamo.
   Además, al cargar el Excel de reclamos se ignoran las líneas repetidas.

Antes de crear la instancia del bot se ejecuta `init_db()` desde
`main.py`. Esta función crea las tablas y ejecuta
`ensure_servicio_columns()` para garantizar que la tabla `servicios`
incluya las columnas `ruta_tracking`, `trackings`, `camaras`, `carrier`,
`id_carrier` y `carrier_id`. Además crea `carrier_id` en
`tareas_programadas` y genera los índices requeridos.

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
`/registrar_tarea <cliente> <inicio> <fin> <tipo> <id1,id2> [carrier]`.
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

Si un carrier cambia de nombre podés actualizarlo antes de registrar nuevas tareas:

```bash
/actualizar_carrier Telco NuevoTelco
```

Para verificar todos los correos asignados a un cliente según su carrier ejecutá:

```bash
/destinatarios_por_carrier ClienteA
```

### Listar tareas programadas

Con `/listar_tareas` podés consultar las ventanas ya registradas.
Los parámetros `cliente`, `servicio` e intervalo de fechas son opcionales
y se pueden combinar libremente. También se acepta `carrier=<nombre>`
para filtrar por carrier.
Ejemplos:

```bash
/listar_tareas ClienteA
/listar_tareas 7 2024-01-01 2024-01-05
/listar_tareas carrier=Telecom
```
El bot muestra inicio, fin, tipo y los servicios afectados.

### Avisos en formato `.MSG`

Al registrar una tarea se genera un archivo `.MSG` con los datos
principales. Este aviso puede abrirse con Outlook y reenviarse o
ajustarse antes de enviarlo. Si `pywin32` está presente, el sistema
aplica la firma ubicada en `SIGNATURE_PATH` y aprovecha Outlook para
formatear el mensaje. Para leer los adjuntos es necesario instalar
`extract-msg`; `pywin32` es opcional, pero permite crear un `.MSG`
real con la firma incluida.
Además Sandy envía el aviso por correo a los destinatarios configurados para el cliente o para el par (cliente, carrier) cuando corresponde.

### Reenviar un aviso de tarea

Si necesitás volver a compartir una ventana ya registrada, ejecutá:

```bash
/reenviar_aviso <id_tarea> [carrier]
```

El bot reconstruirá el mensaje y lo enviará a los contactos del cliente.
Además adjuntará el archivo `.MSG` en el chat para facilitar el reenvío manual.


### Procesar correos y registrar tareas

Usá `/procesar_correos` para analizar los avisos `.MSG` que reciba el bot y evitar cargar la información de forma manual. El comando extrae los datos mediante GPT y reenvía automáticamente el aviso a los destinatarios configurados.

Si `pywin32` está instalado los `.MSG` se crean con Outlook, por lo que podés abrirlos y editar el cuerpo antes de enviarlos. Sin esas librerías el bot genera un texto plano.

Por ejemplo:
```bash
/procesar_correos Cliente
```
Luego adjuntá uno o varios archivos `.msg` con las ventanas de mantenimiento. Un aviso típico luce así:

```
Estimado Cliente, nuestro partner nos da aviso de la siguiente tarea programada:
Inicio: 2024-01-02 08:00
Fin: 2024-01-02 10:00
Tipo de tarea: Mantenimiento
Servicios afectados: 42
```

### Detectar tareas desde un correo

Con `/detectar_tarea <cliente> [carrier]` podés pegar el mail o adjuntar el archivo.
Sandy utiliza GPT para extraer inicio, fin, tipo y los IDs de servicio.
Al crear la tarea genera también un `.MSG` con el texto listo para enviar.


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
Esta opción recibe un Excel con las columnas "ID Servicio" y "Carrier".
El bot registra cada carrier, lo vincula al servicio mediante `carrier_id` y
devuelve el archivo actualizado con los datos completados.

## Administración de carriers y destinatarios

Podés crear carriers manualmente con `/agregar_carrier <nombre>`, consultarlos
mediante `/listar_carriers`, renombrarlos con `/actualizar_carrier <viejo> <nuevo>`
y borrarlos con `/eliminar_carrier <nombre>`.
Los contactos de cada cliente se gestionan con:

```
/agregar_destinatario <cliente> <correo> [carrier]
/eliminar_destinatario <cliente> <correo> [carrier]
/listar_destinatarios <cliente> [carrier]
/destinatarios_por_carrier <cliente>
```

Si indicás un carrier, el correo queda asociado únicamente a ese proveedor. De
lo contrario se guarda como destinatario general del cliente. Cuando se envían
avisos, Sandy prioriza la lista específica si existe para el `(cliente, carrier)`.

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

## Informe de SLA

Este flujo genera un reporte basado en el documento `Template Informe SLA.docx`, ubicado por defecto en `Sandy bot/templates`. Para iniciarlo presioná **Informe de SLA** en el menú principal o ejecutá `/informe_sla`.
Al activarse se usa la plantilla indicada por `SLA_TEMPLATE_PATH`. Si no se define, se toma `Sandy bot/templates/Template Informe SLA.docx`.
El archivo debe existir en formato `.docx`.

El bot solicitará primero el Excel de **reclamos** y luego el de **servicios**. Estos archivos se pueden enviar por separado. Una vez que el bot recibe ambos aparecerá el botón **Procesar**, que genera el informe utilizando la plantilla configurada en `SLA_TEMPLATE_PATH`. El documento se crea automáticamente con los campos de **Eventos destacados**, **Conclusión** y **Propuesta de mejora** en blanco.


```env
SLA_TEMPLATE_PATH=/ruta/personalizada/Template SLA.docx
```

Las plantillas por defecto se guardan en `templates/`. Al presionar
**Actualizar plantilla** el archivo actual se copia a `templates/Historicos`
y la nueva versión queda disponible para informes futuros.

Si la ruta no es válida se mostrará el error "Plantilla de SLA no encontrada" y el proceso se cancelará.

### Ejemplo completo del flujo

1. Enviá el Excel con los **reclamos** y luego el de **servicios**.
2. Una vez recibidos ambos, el bot muestra los botones **Procesar** y **Exportar a PDF**.
3. Al presionar alguna opción se genera el documento con un nombre del tipo `InformeSLA_<fecha>_<n>`. La tabla principal de servicios se ordena de forma descendente por la columna **SLA**. Este criterio debe mantenerse en cada implementación.
   Si se llama a `_generar_documento_sla(exportar_pdf=True)` con `pywin32` en Windows o con `docx2pdf` en otros sistemas, también se guarda la versión PDF.
4. Finalmente el archivo se envía por Telegram y se elimina automáticamente del sistema para evitar residuos.
5. En cualquier momento se puede usar el botón **Actualizar plantilla** para cargar una nueva base en formato `.docx`.

### Exportar informe a PDF

Para obtener una versión en PDF instalá `docx2pdf` o, si usás Windows, el paquete opcional `pywin32`.
Una vez generada la plantilla podés presionar el botón **Exportar PDF** o llamar a
`_generar_documento_sla(exportar_pdf=True)` para producir el archivo.
El flujo consiste en enviar primero el Excel de **reclamos**, luego el de **servicios**,
presionar **Procesar** y finalmente optar por **Exportar PDF**.
Recordá que la plantilla se puede reemplazar en cualquier momento con el botón **Actualizar plantilla**.
Cuando uses esa opción, el archivo anterior se moverá a `templates/Historicos` y la nueva plantilla quedará almacenada en `templates/`.


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
Las dependencias externas como `openpyxl`, `python-docx` y `pandas` se utilizan en algunas pruebas,
pero no son obligatorias gracias a los stubs incluidos.

Antes de ejecutar `pytest` es **necesario** preparar el entorno con `setup_env.sh`.
El script crea el virtualenv en `.venv`, instala las dependencias de
`Sandy bot/requirements.txt` y exporta la ruta `Sandy bot` en `PYTHONPATH`
para que las importaciones funcionen sin ajustes manuales.

```bash
./setup_env.sh
pytest
```

Si preferís no ejecutar el script, asegurate de instalar manualmente las dependencias con:

```bash
pip install -r "Sandy bot/requirements.txt"
```
Antes de lanzar `pytest` para evitar errores de importación.

Algunas pruebas relacionadas con la base de datos se omiten de forma automática si `SQLAlchemy`
no está presente en el entorno.


## Licencia

Este proyecto se publica bajo la licencia [MIT](LICENSE).

