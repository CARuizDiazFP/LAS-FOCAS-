# SandyBot

Bot de Telegram para gestión de infraestructura de fibra óptica.

## Características

- Integración con Telegram usando python-telegram-bot
- Procesamiento de lenguaje natural con GPT-4
- Base de datos PostgreSQL para historial de conversaciones
- `init_db()` crea las tablas y ejecuta `ensure_servicio_columns()`
  para verificar que la tabla `servicios` incluya las columnas
  `ruta_tracking`, `trackings`, `camaras`, `carrier` e `id_carrier`
- Procesamiento de archivos Excel para informes
- Generación de documentos Word
- Integración con Notion para seguimiento de solicitudes

## Requisitos

- Python 3.9+
- PostgreSQL
- Microsoft Word (para informes de repetitividad)
- Paquete `openai` versión 1.0.0 o superior

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
```

## Uso

Para iniciar el bot:

```bash
python main.py
```

Al ejecutarse, `main.py` configura automáticamente el sistema de logging. Los
mensajes se muestran en la consola utilizando el formato estándar de Python.

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

La función `init_db()` crea las tablas automáticamente y ejecuta
`ensure_servicio_columns()` para asegurar que la tabla `servicios`
contenga las columnas `ruta_tracking`, `trackings`, `camaras`, `carrier`
e `id_carrier`.

- **Conversacion**: guarda los mensajes del bot y las respuestas.
- **Servicio**: almacena nombre, cliente, carrier e ID carrier, además
  de las cámaras, los trackings y la ruta al informe de comparación.

## Comandos

- `/start`: Muestra el menú principal
- `/procesar`: Procesa archivos en modo comparador
- `/cargar_tracking`: Asocia un tracking a un servicio existente

## Funcionalidades

1. Comparación de trazados FO
   - En el menú principal elegí "Comparar trazados FO"
   - Adjuntá los trackings en formato `.txt`
   - Ejecutá `/procesar` para recibir un Excel con coincidencias y el listado de cámaras

2. Verificación de ingresos
   - Valida ingresos contra trazados
   - Genera informe de coincidencias
   - Detecta duplicados
   - También podés buscar un servicio escribiendo el nombre de la cámara
3. Carga de tracking
   - Seleccioná "Cargar tracking" en el menú principal
   - Enviá el archivo `.txt` cuyo nombre contenga el ID (ej.: `FO_1234_tramo.txt`)
   - El bot mostrará dos botones: **Procesar tracking** para usar el ID detectado
     o **Modificar ID** para ingresar otro número manualmente. También podés
     confirmar escribiendo "sí" o "si".
   - Si el ID no existe en la base, Sandy lo registrará automáticamente.

4. Informes de repetitividad
   - Procesa Excel de casos
   - Genera informe Word
   - Identifica líneas con reclamos múltiples
   - Nota: la modificación automática del documento usa `win32com` y solo
     funciona en Windows. En otros sistemas puede generarse el archivo .docx
     sin esta modificación o realizar los cambios de forma manual.

5. Consultas generales
   - Respuestas técnicas con GPT
   - Tono malhumorado característico
   - Registro de conversaciones

## Contribuir

1. Fork del repositorio
2. Crear rama (`git checkout -b feature/nombre`)
3. Commit cambios (`git commit -am 'Add: descripción'`)
4. Push a la rama (`git push origin feature/nombre`)
5. Crear Pull Request

## Licencia

Este proyecto está licenciado bajo [insertar licencia].
