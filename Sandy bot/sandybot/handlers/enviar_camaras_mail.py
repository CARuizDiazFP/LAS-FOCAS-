# Nombre de archivo: enviar_camaras_mail.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/enviar_camaras_mail.py
# User-provided custom instructions
"""Manejadores para enviar las cámaras de un servicio por correo electrónico."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import os
import tempfile
from sqlalchemy.exc import SQLAlchemyError

from ..config import config

from ..utils import obtener_mensaje
from ..database import exportar_camaras_servicio
from ..registrador import responder_registrando, registrar_conversacion
from .estado import UserState
from ..email_utils import enviar_excel_por_correo

logger = logging.getLogger(__name__)


async def iniciar_envio_camaras_mail(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Solicita ID de servicio y correo para enviar el Excel."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_envio_camaras_mail.")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "enviar_camaras_mail")
    context.user_data.clear()
    await responder_registrando(
        mensaje,
        user_id,
        "enviar_camaras_mail",
        "Escribí el ID del servicio y el mail destino separados por espacio.\nEjemplo: 123 usuario@dominio.com",
        "enviar_camaras_mail",
    )


async def procesar_envio_camaras_mail(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Genera el Excel de cámaras y lo envía por correo."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.text:
        logger.warning("Datos faltantes en procesar_envio_camaras_mail.")
        return

    partes = mensaje.text.strip().split()
    if len(partes) != 2 or not partes[0].isdigit():
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            mensaje.text,
            "Debes indicar ID y correo separados por espacio.",
            "enviar_camaras_mail",
        )
        return

    id_servicio = int(partes[0])
    correo = partes[1]
    ruta = os.path.join(tempfile.gettempdir(), f"camaras_{mensaje.from_user.id}.xlsx")
    try:
        ok = exportar_camaras_servicio(id_servicio, ruta)
    except SQLAlchemyError as e:
        logger.error("Error al exportar cámaras: %s", e)
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            mensaje.text,
            "No pude conectarme a la base de datos. Verificá la configuración.",
            "enviar_camaras_mail",
        )
        return
    if not ok or not os.path.exists(ruta):
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            mensaje.text,
            "No hay cámaras registradas para ese servicio.",
            "enviar_camaras_mail",
        )
        return

    try:
        enviar_excel_por_correo(
            correo,
            ruta,
            asunto="Listado de cámaras",
            cuerpo="Adjunto las cámaras solicitadas.",
        )
        registrar_conversacion(
            mensaje.from_user.id,
            mensaje.text,
            f"Cámaras enviadas a {correo}",
            "enviar_camaras_mail",
        )
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            mensaje.text,
            f"📧 Cámaras enviadas a {correo}",
            "enviar_camaras_mail",
        )
    except Exception as e:
        logger.error("Error enviando cámaras por mail: %s", e)
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            mensaje.text,
            f"Error al enviar el mail: {e}",
            "enviar_camaras_mail",
        )
    finally:
        UserState.set_mode(update.effective_user.id, "")
        context.user_data.clear()
        if os.path.exists(ruta):
            os.remove(ruta)
