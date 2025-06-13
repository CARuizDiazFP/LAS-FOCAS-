# + Nombre de archivo: start.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/start.py
# User-provided custom instructions
"""
Handler principal para el comando /start
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..registrador import responder_registrando

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start mostrando el menú principal"""
    keyboard = [
        [
           InlineKeyboardButton("📊 Comparar trazados FO", callback_data="comparar_fo"),
           InlineKeyboardButton("📥 Verificar ingresos", callback_data="verificar_ingresos"),
           InlineKeyboardButton("📌 Registro de ingresos", callback_data="registro_ingresos"),
        ],
        [
           InlineKeyboardButton("📂 Cargar tracking", callback_data="cargar_tracking"),
           InlineKeyboardButton("⬇️ Descargar tracking", callback_data="descargar_tracking"),
        ],
        [
           InlineKeyboardButton("⬇️ Descargar cámaras", callback_data="descargar_camaras"),
           InlineKeyboardButton("📧 Enviar cámaras por mail", callback_data="enviar_camaras_mail"),
        ],
        [
           InlineKeyboardButton(
               "Identificador de servicio Carrier", callback_data="id_carrier"
           ),
           InlineKeyboardButton(
               "🔍 Identificar tarea programada",
               callback_data="identificador_tarea",
           ),
        ],
        [
           InlineKeyboardButton("🔁 Informe de repetitividad", callback_data="informe_repetitividad"),
           InlineKeyboardButton("🦜 Informe de SLA", callback_data="informe_sla"),
        ],
        [
           InlineKeyboardButton("📝 Analizar incidencias", callback_data="analizar_incidencias"),
        ],
        [
            InlineKeyboardButton("💬 Otro", callback_data="otro"),
            InlineKeyboardButton("📝 Nueva solicitud", callback_data="nueva_solicitud"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await responder_registrando(
        update.message,
        update.effective_user.id,
        "/start",
        "Bienvenido al menú principal. ¿Qué acción deseas realizar?",
        "start",
        reply_markup=reply_markup,
    )
