# SandyBot

Bot de Telegram para gestión de infraestructura de fibra óptica.

## Características

- Integración con Telegram usando python-telegram-bot
- Procesamiento de lenguaje natural con GPT-4
- Base de datos PostgreSQL para historial de conversaciones.
- `init_db()` se ejecuta desde `main.py` para crear las tablas y
  ejecutar `ensure_servicio_columns()`. Esto verifica que la tabla
  `servicios` incluya las columnas `ruta_tracking`, `trackings`,
  `camaras`, `carrier` e `id_carrier`. Las columnas de cámaras y
  trackings utilizan `JSONB` y permiten guardar listas sin convertirlas a
  texto
- Procesamiento de archivos Excel para informes
- Generación de documentos Word
- Integración con Notion para seguimiento de solicitudes
- Registro de interacciones para ajustar el tono de las respuestas
- Transcripción de mensajes de voz usando la API de OpenAI

## Requisitos

- Python 3.9+
- PostgreSQL
- Microsoft Word (para informes de repetitividad)
- Paquete `openai` versión 1.0.0 o superior

Para que el bot funcione correctamente la base de datos debe contar con las
extensiones `unaccent` y `pg_trgm`. El usuario usado por SandyBot tiene que
tener permisos suficientes para crearlas o bien un administrador debe
habilitarlas de antemano. Los comandos son:

```sql
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

La función `immutable_unaccent` que crea `database.py` invoca
`public.unaccent`. Si instalás la extensión en otro esquema,
ajustá la instrucción para utilizar el nombre completo correspondiente.

## Instalación

1. Clonar el repositorio:
```bash
git clone [url-del-repo]
cd sandybot
```

2. Crear entorno virtual:
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Crear archivo .env con las variables de entorno:
```
TELEGRAM_TOKEN=your_telegram_token
OPENAI_API_KEY=your_openai_key
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_notion_db_id
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sandybot
DB_USER=your_db_user
DB_PASSWORD=your_db_password
PLANTILLA_PATH=C:\Metrotel\Sandy\plantilla_informe.docx
SLA_TEMPLATE_PATH=C:\Metrotel\Sandy\Template Informe SLA.docx
```

## Uso

Para iniciar el bot:

```bash
python main.py
```

Al ejecutarse, `main.py` configura automáticamente el sistema de logging. Los
mensajes se muestran en la consola y además se guardan en `logs/sandy.log` con
rotación automática. Los errores a partir de nivel `ERROR` también se registran
en `logs/errores_ingresos.log` para facilitar el diagnóstico.

## Estructura

```
sandybot/
├── __init__.py           # Package initialization
├── bot.py               # Main bot class
├── config.py            # Configuration management
├── database.py          # Database models and setup
├── gpt_handler.py       # GPT integration
├── handlers/            # Telegram handlers
│   ├── __init__.py
│   ├── callback.py      # Button callbacks
│   ├── comparador.py    # FO trace comparison
│   ├── document.py      # Document processing
│   ├── estado.py        # User state management
│   ├── ingresos.py      # Entry verification
│   ├── message.py       # Text messages
│   ├── notion.py        # Notion integration
│   ├── repetitividad.py # Repetition reports
│   └── start.py        # Start command
└── utils.py            # Utility functions
```

## Modelos de base de datos

La función `init_db()` se ejecuta al inicio desde `main.py` para crear las
tablas y llamar a `ensure_servicio_columns()`. Esto garantiza que la tabla
`servicios` incluya las columnas `ruta_tracking`, `trackings`, `camaras`,
`carrier` e `id_carrier`. Las cámaras y los trackings se almacenan como
`JSONB`, por lo que se admiten listas de forma nativa sin procesamiento
adicional.

- **Conversacion**: guarda los mensajes del bot y las respuestas.
- **Servicio**: almacena nombre, cliente, carrier e ID carrier, además
  de las cámaras, los trackings y la ruta al informe de comparación.

## Comandos

- `/start`: Muestra el menú principal
- `/procesar`: Procesa archivos en modo comparador
- `/cargar_tracking`: Asocia un tracking a un servicio existente
- `/descargar_tracking`: Descarga el tracking asociado a un servicio
- `/descargar_camaras`: Exporta las cámaras registradas para un servicio
- `/comparar_fo`: Inicia la comparación de trazados

## Funcionalidades

1. Comparación de trazados FO
   - En el menú principal elegí "Comparar trazados FO"
   - Podés iniciarlo también con `/comparar_fo` o escribiendo "Comparar FO"
   - Adjuntá los trackings en formato `.txt`
   - Al detectar un servicio con tracking existente aparecerá el botón **Siguiente ➡️** para mantenerlo
   - Ejecutá `/procesar` o presioná el botón **Procesar 🚀** para recibir un Excel con coincidencias y el listado de cámaras

2. Verificación de ingresos
   - Valida ingresos contra trazados
   - Genera informe de coincidencias
   - Detecta duplicados
   - También podés buscar un servicio escribiendo el nombre de la cámara
   - La verificación no distingue entre mayúsculas y minúsculas
   - También podés cargar un Excel con un lote de cámaras en la columna A
   - Informa si se accedió a otra "botella" (Bot 2, Bot 3, ... ) de la misma cámara
3. Carga de tracking
   - Seleccioná "Cargar tracking" en el menú principal
   - Enviá el archivo `.txt` cuyo nombre contenga el ID (ej.: `FO_1234_tramo.txt`)
   - El bot mostrará dos botones: **Procesar tracking** para usar el ID detectado
     o **Modificar ID** para ingresar otro número manualmente. También podés
     confirmar escribiendo "sí" o "si".
   - Si el ID no existe en la base, Sandy lo registrará automáticamente.
4. Descarga de tracking
   - Elegí "Descargar tracking" desde el menú o escribí `/descargar_tracking`
   - Indicá el número de servicio y recibirás el `.txt` si está disponible
   - Con `enviar_tracking_reciente_por_correo()` podés recibir por mail el
     último archivo del histórico con nombre `Tracking_ID_DDMMAAAA_NN.txt`.
5. Descarga de cámaras
   - Seleccioná "Descargar cámaras" desde el menú o enviá `/descargar_camaras`
   - Indicá el ID y recibirás un Excel con todas las cámaras asociadas
   - También podés usar `/enviar_camaras_mail` para recibirlas por correo.
   - Los archivos se nombran `Camaras_ID_DDMMAAAA_NN.xlsx` según un contador
     diario.

6. Informes de repetitividad
   - Procesa Excel de casos
   - Genera informe Word
   - Identifica líneas con reclamos múltiples
   - Nota: la modificación automática del documento usa `win32com` y solo
     funciona en Windows. En otros sistemas puede generarse el archivo .docx
     sin esta modificación o realizar los cambios de forma manual.
7. Informe de SLA
   - Genera un resumen de nivel de servicio usando `Template Informe SLA.docx`
   - Podés iniciarlo desde el botón **Informe de SLA** o con `/informe_sla`
   - Solicita los Excel de reclamos y servicios, que pueden enviarse por separado
   - Una vez cargados los dos archivos aparece el botón **Procesar**, que genera el informe según `SLA_TEMPLATE_PATH` con los campos de eventos, conclusión y mejora en blanco


8. Consultas generales
   - Respuestas técnicas con GPT
   - Tono adaptado según interacciones (de cordial a muy malhumorado)
   - Registro de conversaciones

## Informe de SLA

Esta opcion genera un documento de nivel de servicio basado en `Template Informe SLA.docx`.
Podes iniciarla desde el boton **Informe de SLA** o con el comando `/informe_sla`.
El bot pedirá primero el Excel de **reclamos** y luego el de **servicios**. Podés enviarlos por separado sin importar el orden.
Cuando ambos estén disponibles aparecerá un botón **Procesar**, que genera el informe usando la plantilla definida en `SLA_TEMPLATE_PATH`. El documento se crea automáticamente con los textos de **Eventos destacados**, **Conclusión** y **Propuesta de mejora** en blanco.
El título del informe se adapta al mes correspondiente en español. Si el documento de plantilla no incluye el estilo `Title`, el bot emplea `Heading 1` como respaldo.
Además se agregó un botón para reemplazar la plantilla actual y otro para exportar el resultado directamente a PDF.


```env
SLA_TEMPLATE_PATH=/ruta/personalizada/Template SLA.docx
```

Si la ruta no existe se mostrará el mensaje "Plantilla de SLA no encontrada" y el proceso finalizará sin generar el informe.

## Pruebas

Para ejecutar la suite de tests primero corré `setup_env.sh`.
Ese script instala las dependencias en `.venv` y configura `PYTHONPATH`.
Antes de correr las pruebas definí algunas variables de entorno mínimas:

```bash
export TELEGRAM_TOKEN=dummy
export OPENAI_API_KEY=dummy
export NOTION_TOKEN=dummy
export NOTION_DATABASE_ID=dummy
export DB_USER=postgres
export DB_PASSWORD=postgres
```

Luego podés lanzar `pytest` normalmente.

```bash
./setup_env.sh
pytest
```

## Contribuir
1. Fork del repositorio
2. Crear rama (`git checkout -b feature/nombre`)
3. Commit cambios (`git commit -am 'Add: descripción'`)
4. Push a la rama (`git push origin feature/nombre`)
5. Crear Pull Request

## Licencia

El código se distribuye bajo la licencia [MIT](../LICENSE).
