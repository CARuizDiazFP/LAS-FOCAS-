"""Handler para descargar trackings guardados."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import os

from ..utils import obtener_mensaje
from ..database import obtener_servicio
from .estado import UserState

logger = logging.getLogger(__name__)

async def iniciar_descarga_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pide al usuario el ID del servicio para enviar el tracking."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_descarga_tracking.")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "descargar_tracking")
    context.user_data.clear()
    await mensaje.reply_text("Indicá el ID del servicio para obtener su tracking.")

async def enviar_tracking_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía el tracking asociado al ID recibido si existe."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.text:
        logger.warning("No se recibió ID de servicio en enviar_tracking_servicio.")
        return

    id_text = mensaje.text.strip()
    if not id_text.isdigit():
        await mensaje.reply_text("El ID debe ser numérico.")
        return

    servicio = obtener_servicio(int(id_text))
    if not servicio or not servicio.ruta_tracking:
        await mensaje.reply_text("No hay tracking guardado para ese servicio.")
        return

    ruta = servicio.ruta_tracking
    if not os.path.exists(ruta):
        await mensaje.reply_text("El archivo de tracking no está disponible.")
        return

    try:
        with open(ruta, "rb") as f:
            await mensaje.reply_document(f, filename=os.path.basename(ruta))
    except Exception as e:
        logger.error("Error al enviar tracking: %s", e)
        await mensaje.reply_text(f"Error al enviar el tracking: {e}")
    finally:
        UserState.set_mode(update.effective_user.id, "")
        context.user_data.clear()
