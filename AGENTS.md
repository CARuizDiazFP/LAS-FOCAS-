# Manual de agentes para SandyBot

## 🧠 Propósito del Bot

Sandy es un agente inteligente que opera en Telegram y automatiza tareas repetitivas dentro del ámbito de las telecomunicaciones. Entre sus funciones principales se encuentran:

- Verificación de ingresos a cámaras de fibra óptica
- Comparación de trazados (trackings)
- Descarga de cámaras del servicio en Excel
- Generación de informes (repetitividad, coincidencias, etc.)
- Identificación de servicio Carrier a partir de archivos Excel. Los datos de
  cada fila se guardan en la base actualizando el `id_carrier` del servicio o
  creando un nuevo registro si es necesario.
- Clasificación de mensajes ambiguos
- Enrutamiento de tareas a Notion cuando no pueden resolverse
- Ajuste de tono según interacciones de cada usuario
- Las acciones de los botones también se pueden activar escribiendo la intención en lenguaje natural
- Desde 2025 la detección de estas intenciones se apoya en palabras clave
  y reglas simples. Gracias a ello frases como "Comparemos trazados de FO"
-  activan automáticamente el flujo "Comparar trazados FO" sin necesidad de
  presionar el botón.
- El diccionario `claves` incluye abreviaturas como "cmp fo", "desc trk" o
  "env cams mail". Se usa `difflib` para tolerar errores menores de tipeo.
- Desde 2026 se añadió un módulo de GPT que intenta identificar el flujo
  correspondiente a partir del texto completo del usuario.
  Si no puede clasificarlo con certeza, genera una pregunta automática
  para aclarar la intención antes de continuar.

## 🎓 Filosofía de diseño

Sandy está pensado para ser:

- **Escalable:** modular, con soporte para PostgreSQL y FastAPI.
- **Conversacional:** emplea lenguaje natural.
- **Asistente híbrido:** combina procesamiento tradicional y GPT.
- **Interoperable:** puede integrarse con Google Sheets, Notion y Slack.


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

> **Tip de desarrollo:** cuando un handler se invoca mediante un callback,
> `obtener_mensaje(update)` devuelve el mensaje del bot que contiene el botón.
> Para asignar el modo correcto al usuario se debe usar
> `update.effective_user.id`.

## ⚙️ Agente principal: `gpt_handler.py`

Desde 2025 este módulo utiliza ``openai.AsyncOpenAI`` para acceder a la nueva API 1.x de OpenAI. Gracias a ello, las consultas se realizan de forma asincrónica y se cuenta con un manejo de errores más sólido.

### Funciones clave

`consultar_gpt_con_lineas(lineas, horas)`:

- Usa la API de OpenAI (GPT-4) para analizar mensajes de texto plano.
- Extrae la hora y el nombre de la cámara en los pedidos de ingreso.
- Filtra mensajes irrelevantes (egresos, mantenimiento o cancelaciones).

`analizar_incidencias(texto)`:
- Resume los eventos enumerando fecha, tarea y responsable en formato JSON.


**Prompt base**

Sos un analista que recibe líneas de texto de un grupo de técnicos.
Tu tarea es identificar los pedidos de ingreso válidos a cámaras, nodos, postes, data center, túneles, etc.
- Si en la línea se solicita ingresar, devolvé un objeto JSON con `hora` y `camara`.
- Si es una salida, egreso o se menciona que no hace falta apertura, devolvé solo `null`.

## 🔹 Flujo de procesamiento de ingresos

1. El usuario activa el bot y selecciona **Verificar ingresos**.
2. El bot pregunta si validará por **nombre de cámara** o con **Excel**.
3. Si elige nombre, envía la cámara para ver los servicios asociados.
4. Si elige Excel, adjunta un `.xlsx` con las cámaras en la columna A.
5. El bot extrae los bloques relevantes y los filtra con expresiones regulares.
6. Si no puede interpretarlos, los envía a GPT-4.
7. El resultado se guarda en un Excel con dos hojas:
   - Hoja 1: todos los ingresos extraídos (hora y cámara).
   - Hoja 2: coincidencias con el tracking cargado.

## 💼 Otros agentes o acciones especiales

- Si el bot no entiende un mensaje, pide más detalles y lo guarda en Notion con estado **Nuevo**.
- Se planea un "modo supervisor" para validar manualmente los ingresos que el bot no pueda interpretar.

## Analizador de incidencias

Este módulo procesa reportes de fallas de campo y resume los eventos detectados. Ahora admite archivos `.docx` y `.doc`, incluso múltiples adjuntos simultáneos. Entre ellos se puede incluir un archivo de contexto o correos electrónicos. En el futuro se consultará una API para obtener los datos automáticamente.

Flujo básico:
1. Seleccionar **Analizador de incidencias** en el menú principal.
2. Adjuntar los documentos con el detalle de la incidencia (se permiten varios adjuntos).
3. El bot analiza los archivos y entrega un documento con la cronología generada por GPT.

## 🧰 Roadmap de inteligencia artificial



### 🔧 Variables clave

- `usuarios_en_modo_ingresos`: mantiene el estado por usuario.
- `archivos_ingresos`: guarda temporalmente los paths de archivos por usuario.
- `interacciones_usuario`: contador de interacciones para modular el tono.

### 📊 KPIs deseados

- Tasa de extracción correcta.
- Cantidad de ingresos descartados por mantenimiento/egreso.
- Coincidencias detectadas con los trackings.
- Cantidad de ingresos que requirieron validación manual.

## 🎨 Ejemplo de entrada para GPT

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

## 📧 Envío de correos

El bot envía listados por email a los contactos guardados en la tabla `clientes`. Los correos se registran con `/agregar_destinatario` y se consultan con `/listar_destinatarios`. Configurá `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` y `SMTP_PASSWORD` junto a `EMAIL_FROM` en el `.env`. Las variables `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER` y `EMAIL_PASSWORD` siguen siendo válidas para compatibilidad.
Definí también `SIGNATURE_PATH` para indicar la firma que se agrega a los mensajes generados.

Al registrar tareas se genera un aviso en formato `.MSG` y se envía de forma automática a los destinatarios correspondientes. Si tenés Outlook y la dependencia opcional `pywin32`, la firma se inserta y podés ajustar el mensaje antes de enviarlo.
El comando `/procesar_correos` analiza esos `.MSG` y registra las tareas en la base sin intervención manual.

### Informe de SLA

La tabla principal del documento SLA siempre debe ordenarse de **mayor a menor** por la columna `SLA`. Cualquier cambio en el generador o las pruebas debe respetar este criterio.


### Convenciones para commits

- Escribir el resumen en español (máximo 60 caracteres).
- Usar prefijos adecuados (`feat:`, `fix:`, `docs:`, etc.).
- De ser necesario, incluir un cuerpo separado por una línea en blanco.

### Encabezado obligatorio en archivos de código

- Incluir al inicio de cada archivo las líneas con `Nombre de archivo`, `Ubicación de archivo` y `User-provided custom instructions`.
- Colocar el encabezado tras la línea shebang (`#!/usr/bin/env python`) si existe.
- No agregarlo en archivos de datos (`*.json`, `destinatarios.json`) ni en `README.md`.
- Estas líneas sirven para identificar rápidamente cada módulo y recordar que se deben seguir las instrucciones personalizadas.
