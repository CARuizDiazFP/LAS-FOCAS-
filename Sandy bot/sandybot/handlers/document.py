"""
Handler para el procesamiento de documentos.
"""
from telegram import Update
from telegram.ext import ContextTypes
from .estado import UserState
from .repetitividad import procesar_repetitividad
from .comparador import recibir_tracking
from .cargar_tracking import guardar_tracking_servicio
from .ingresos import procesar_ingresos

async def manejar_documento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja el procesamiento de documentos.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        if not update.message:
            return

        user_id = update.message.from_user.id
        mode = UserState.get_mode(user_id)
        if mode == "repetitividad":
            await procesar_repetitividad(update, context)
            return
        if mode == "comparador":
            await recibir_tracking(update, context)
            return
        if mode == "cargar_tracking":
            await guardar_tracking_servicio(update, context)
            return
        if mode == "ingresos":
            await procesar_ingresos(update, context)
            return

        # Lógica para el procesamiento de documentos
        await update.message.reply_text("Procesamiento de documentos en desarrollo.")
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"Error al procesar el documento: {e}")

# Alias para exportar manejar_documento como document_handler
document_handler = manejar_documento
