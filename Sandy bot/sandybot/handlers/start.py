"""
Handler principal para el comando /start
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start mostrando el menú principal"""
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
    await update.message.reply_text(
        "Bienvenido al menú principal. ¿Qué acción deseas realizar?",
        reply_markup=reply_markup
    )
