AGENTS.md

🧠 Propósito del Bot: Sandy

Sandy es un agente inteligente que opera en Telegram, diseñado para ayudar en entornos laborales de telecomunicaciones. Automatiza tareas repetitivas como:

Verificación de ingresos a cámaras de fibra óptica

Comparación de trazados (trackings)

Generación de informes (repetitividad, coincidencias, etc.)

Clasificación de mensajes ambiguos

Enrutamiento de tareas a Notion cuando no pueden resolverse

🎓 Filosofía de diseño

Sandy está pensado para ser:

Escalable: Modular, con soporte para PostgreSQL y FastAPI

Conversacional: Se comunica usando lenguaje natural

Asistente híbrido: Mezcla procesamiento tradicional y GPT

Interoperable: Puede integrarse con Google Sheets, Notion, Slack

⚙️ Agente principal: GPT Handler

Archivo: gpt_handler.py

Desde 2025 este archivo emplea ``openai.AsyncOpenAI`` para comunicarse con la
nueva API 1.x de OpenAI, permitiendo consultas asincrónicas y un manejo de
errores más robusto.

Funciones clave:

consultar_gpt_con_lineas(lineas, horas):

Usa la API de OpenAI (GPT-4) para analizar mensajes de texto plano

Extrae hora y nombre de la cámara en pedidos de ingreso

Filtra mensajes irrelevantes (egresos, mantenimiento, cancelaciones)

Prompt base:

Sos un analista que recibe líneas de texto de un grupo de técnicos.
Tu tarea es identificar los pedidos de ingreso válidos a cámaras, nodos, postes, data center, túneles, etc.
- Si en la línea se solicita ingresar, devolvé un objeto JSON con 'hora' y 'camara'.
- Si es una salida, egreso o se menciona que no hace falta apertura, devolvé solo null.

🔹 Flujo de procesamiento de ingresos

El usuario activa el bot y selecciona "Verificar ingresos"

Envía un archivo .txt con mensajes de Slack (ingresos)

El bot:

Extrae bloques relevantes

Los filtra con expresiones regulares

Si no los puede interpretar, los envía a GPT-4

El resultado se guarda en un Excel:

Hoja 1: Todos los ingresos extraídos (hora, cámara)

Hoja 2: Coincidencias con el tracking cargado

🔹 Carga de tracking

Al ejecutar `/cargar_tracking` se envía directamente el archivo `.txt` del
tracking. El bot extrae el ID desde el nombre (por ejemplo `FO_1234_tramo.txt`)
y consulta si se desea asociarlo a ese servicio. Se puede confirmar con "sí" o
especificar otro ID.

💼 Otros agentes o acciones especiales

Si el bot no entiende un mensaje, pide más detalles y lo guarda en Notion con estado Nuevo

Hay planes para crear un "modo supervisor" para validar manualmente ingresos que el bot no puede interpretar

🧰 Roadmap de inteligencia artificial



🔧 Variables clave

usuarios_en_modo_ingresos: mantiene el estado por usuario

archivos_ingresos: guarda temporalmente los paths de archivos por usuario

📊 KPIs deseados

Tasa de extracción correcta

Cantidad de ingresos descartados por mantenimiento/egreso

Coincidencias detectadas con los trackings

Cantidad de ingresos que requirieron validación manual

🎨 Ejemplo de entrada GPT:

0:37 bot túnel est. Malabia LB corrientes 5448
9:56 Data Tacuari
Se cancela apertura
Mantenimiento sin acceso

Salida esperada:

[
  {"hora": "0:37", "camara": "Bot túnel est. Malabia LB corrientes 5448"},
  {"hora": "9:56", "camara": "Data Tacuari"},
  null,
  null
]

☑️ Este documento debe mantenerse actualizado a medida que Sandy evoluciona. Puedes encontrarlo en AGENTS.md en la raíz del repositorio.