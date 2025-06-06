"""Handler para descargar trackings guardados."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import os

from ..utils import obtener_mensaje
from ..database import obtener_servicio
from ..registrador import responder_registrando, registrar_conversacion
from .estado import UserState
from ..registrador import responder_registrando

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
    await responder_registrando(
        mensaje,
        user_id,
        "descargar_tracking",
        "Indicá el ID del servicio para obtener su tracking.",
        "descargar_tracking",
    )

async def enviar_tracking_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía el tracking asociado al ID recibido si existe."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.text:
        logger.warning("No se recibió ID de servicio en enviar_tracking_servicio.")
        return

    id_text = mensaje.text.strip()
    if not id_text.isdigit():
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            id_text,
            "El ID debe ser numérico.",
            "descargar_tracking",
        )
        return

    servicio = obtener_servicio(int(id_text))
    if not servicio or not servicio.ruta_tracking:
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            id_text,
            "No hay tracking guardado para ese servicio.",
            "descargar_tracking",
        )
        return

    ruta = servicio.ruta_tracking
    if not os.path.exists(ruta):
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            id_text,
            "El archivo de tracking no está disponible.",
            "descargar_tracking",
        )
        return

    try:
        with open(ruta, "rb") as f:
            await mensaje.reply_document(f, filename=os.path.basename(ruta))
        registrar_conversacion(
            mensaje.from_user.id,
            id_text,
            f"Documento {os.path.basename(ruta)} enviado",
            "descargar_tracking",
        )
    except Exception as e:
        logger.error("Error al enviar tracking: %s", e)
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            id_text,
            f"Error al enviar el tracking: {e}",
            "descargar_tracking",
        )
    finally:
        UserState.set_mode(update.effective_user.id, "")
        context.user_data.clear()
