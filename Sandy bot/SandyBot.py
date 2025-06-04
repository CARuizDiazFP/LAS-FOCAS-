# SandyBot.py
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Third-party imports
import openai
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from notion_client import Client as NotionClient

# Local imports
from sandybot.registrador import registrar_conversacion
from sandybot.handlers.repetitividad import procesar_repetitividad
from sandybot.handlers.comparador import iniciar_comparador, recibir_tracking, procesar_comparacion
from sandybot.handlers.ingresos import iniciar_verificacion_ingresos, procesar_ingresos, recibir_archivo as recibir_archivo_ingresos
from sandybot.handlers.estado import (
    usuarios_en_modo_comparador,
    archivos_por_usuario,
    usuarios_en_modo_repetitividad,
    usuarios_en_modo_sandy,
    usuarios_esperando_detalle,
    usuarios_en_modo_ingresos  
)

# Import the centralized config
from sandybot.config import Config

# Inicialización
config = Config()
notion = NotionClient(auth=config.NOTION_TOKEN)

# Ruta del archivo donde se guarda el contador
ARCHIVO_CONTADOR = "contador_diario.json"

# Estado temporal por usuario

# ============================
# FUNCIONES AUXILIARES
# ============================

def cargar_contador():
    if os.path.exists(ARCHIVO_CONTADOR):
        with open(ARCHIVO_CONTADOR, "r") as f:
            return json.load(f)
    return {}

def guardar_contador(contador):
    with open(ARCHIVO_CONTADOR, "w") as f:
        json.dump(contador, f)

def registrar_accion_pendiente(mensaje_usuario, telegram_id):
    try:
        fecha_actual = datetime.now().strftime("%d-%m-%Y")
        contador = cargar_contador()
        if fecha_actual not in contador:
            contador[fecha_actual] = 1
        else:
            contador[fecha_actual] += 1
        guardar_contador(contador)

        id_solicitud = f"{contador[fecha_actual]:03d}"
        nombre_solicitud = f"Solicitud{id_solicitud}{datetime.now().strftime('%d%m%y')}"

        nueva_entrada = {
            "parent": {"database_id": config.NOTION_DATABASE_ID},
            "properties": {
                "Nombre": {
                    "title": [{"text": {"content": nombre_solicitud}}]
                },
                "Estado": {"select": {"name": "Nuevo"}},
                "Fecha": {"date": {"start": datetime.now().isoformat()}},
                "ID Telegram": {
                    "rich_text": [{"text": {"content": str(telegram_id)}}]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": mensaje_usuario}}]
                    }
                }
            ]
        }

        notion.pages.create(**nueva_entrada)
        logger.info("✅ Acción pendiente registrada como %s", nombre_solicitud)

    except Exception as e:
        logger.error("❌ Error al registrar en Notion: %s", str(e))
        raise

# Usar el GPTHandler mejorado del módulo gpt_handler
from sandybot.gpt_handler import gpt as gpt_handler

# Usar el logger raíz configurado en `main.py`
logger = logging.getLogger(__name__)

# ============================
# MANEJADORES TELEGRAM
# ============================

# MENÚ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📊 Comparar trazados FO", callback_data="comparar_fo"),
            InlineKeyboardButton("📥 Verificar ingresos", callback_data="verificar_ingresos"),
        ],
        [
           InlineKeyboardButton("🔁 Informe de repetitividad", callback_data="informe_repetitividad"),
           InlineKeyboardButton("🦜 Informe de SLA", callback_data="informe_sla"),
        ],
        [
            InlineKeyboardButton("💬 Otro", callback_data="otro"),
            InlineKeyboardButton("📝 Nueva solicitud", callback_data="nueva_solicitud"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Bienvenido al menú principal. ¿Qué acción deseas realizar?", reply_markup=reply_markup)

# RESPUESTAS A BOTONES
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "comparar_fo":
        await iniciar_comparador(update, context)
    elif query.data == "verificar_ingresos":
        await iniciar_verificacion_ingresos(update, context)
    elif query.data == "informe_repetitividad":
        user_id = query.from_user.id
        usuarios_en_modo_repetitividad[user_id] = True
        await query.edit_message_text("📂 Adjuntá el archivo Excel para generar el informe. No te equivoques, ¿sí?")

    elif query.data == "informe_sla":
        await query.edit_message_text("🔧 Función 'Informe de SLA' aún no implementada.")


    elif query.data == "otro":
        user_id = query.from_user.id
        usuarios_en_modo_sandy[user_id] = True
        await query.edit_message_text("¿Para qué me jodés? Indique su pregunta o solicitud. Si no puedo hacerla, se enviará como solicitud de implementación.")
  
    elif query.data == "procesar_comparacion":
        await query.edit_message_text("🛠 Procesando archivos...")
        await procesar_comparacion(update, context)

    elif query.data == "seguir_adjuntando":
        await query.answer("Seguí mandando archivos nomás.")

    elif query.data == "nueva_solicitud":
        await query.edit_message_text("📝 Función 'Nueva solicitud' aún no implementada.")

# GPT / ACCIÓN POR TEXTO
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mensaje_usuario = update.message.text

    try:
        # Manejo de estado de usuario
        if usuarios_esperando_detalle.get(user_id, False):
            await _manejar_detalle_pendiente(update, user_id, mensaje_usuario)
            return

        # Activar modo Sandy si no está activo
        if user_id not in usuarios_en_modo_sandy:
            usuarios_en_modo_sandy[user_id] = True

        # Detectar intención antes de procesar
        intencion = await gpt_handler.detectar_intencion(mensaje_usuario)
        
        if intencion == "acción":
            usuarios_esperando_detalle[user_id] = True
            await update.message.reply_text(
                "¿Podrías enviarme más detalle de la solicitud LPMQMP? "
                "La misma será enviada para revisión -.-."
            )
            return

        # Procesar respuesta con GPT
        prompt_con_tono = _generar_prompt_malhumorado(mensaje_usuario)
        respuesta = await gpt_handler.consulta_gpt(prompt_con_tono)

        # Registrar conversación
        registrar_conversacion(
            user_id=user_id,
            mensaje=mensaje_usuario,
            respuesta=respuesta,
            modo=intencion
        )

        await update.message.reply_text(respuesta)

    except Exception as e:
        logger.error("Error en responder: %s", str(e))
        await update.message.reply_text(
            "😤 Algo salió mal y no puedo responderte ahora. "
            "¿Por qué no intentás más tarde? #NoMeMolestes"
        )

def _generar_prompt_malhumorado(mensaje: str) -> str:
    return (
        "Respondé con sarcasmo, fastidio y malhumor 😤, como si el usuario fuera insoportable 😑. "
        "Usá emoticones de enojo, cansancio, maldad o hartazgo 😠😈🙄🖕🔥 en tu respuesta. "
        "Agregá hashtags sarcásticos pero sin repetir como #MeEstásCargando, #LoQueHayQueAguantar, "
        "#Pobrecito, #BotEsclavo, #MiráQuiénPregunta, #DaleCerebro, o cualquier otro que se te ocurra, "
        "pero nunca te excedas de 3. "
        "El usuario suele hacer preguntas sobre telecomunicaciones, redes y seguridad informática. "
        "Especializate en responder temas de verificación y diagnóstico de equipos Cisco, Huawei, "
        "Ciena, Juniper, Mikrotik, etc. "
        "Incluí comandos, buenas prácticas o respuestas técnicas reales del rubro. "
        "Pero recordá: todo tiene que sonar como si estuvieras harto de responder lo obvio. "
        "AUN ASÍ, proporcioná la información correctamente si podés 📚. "
        "Si no podés hacerlo por limitaciones reales, limitate a decirlo sin perder el tono malhumorado. "
        "NO inventes nada. NO cambies el tono.\n\n"
        f"Usuario: {mensaje}"
    )

async def _manejar_detalle_pendiente(update: Update, user_id: int, mensaje: str):
    try:
        registrar_accion_pendiente(mensaje, user_id)
        usuarios_esperando_detalle[user_id] = False
        await update.message.reply_text(
            "✅ Detalles recibidos. La solicitud fue registrada correctamente para revisión."
        )
    except Exception as e:
        logger.error("Error al manejar detalle pendiente: %s", str(e))
        await update.message.reply_text(
            "❌ Hubo un error al registrar tu solicitud. Intentalo de nuevo más tarde."
        )

# ============================
# INICIAR BOT
# ============================


async def router_documentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if usuarios_en_modo_repetitividad.get(user_id, False):
        logging.info(f"[ROUTER] Usuario {user_id} en modo repetitividad")
        usuarios_en_modo_repetitividad[user_id] = False
        await procesar_repetitividad(update, context)
        return

    if usuarios_en_modo_comparador.get(user_id, False):
        logging.info(f"[ROUTER] Usuario {user_id} en modo comparador")
        await recibir_tracking(update, context)
        return

    if usuarios_en_modo_ingresos.get(user_id, False):
        logging.info(f"[ROUTER] Usuario {user_id} en modo ingresos")
        await recibir_archivo_ingresos(update, context)
        return

    # Si no está en ningún modo esperado
    logging.info(f"[ROUTER] Usuario {user_id} fuera de contexto. Ignorado.")
    await update.message.reply_text("¿Y esto qué es? Si querés que haga algo, usá el menú primero. 😒")



if __name__ == '__main__':
    try:
        config = Config()
        app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
        app.add_handler(MessageHandler(filters.Document.ALL, router_documentos))
        app.add_handler(CommandHandler("procesar", procesar_comparacion))

        logger.info("Bot iniciado correctamente")
        app.run_polling()
    except Exception as e:
        logger.error("Error al iniciar el bot: %s", str(e))
