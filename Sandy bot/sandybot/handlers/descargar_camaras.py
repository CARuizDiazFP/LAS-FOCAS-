"""Handler para descargar las cámaras de un servicio en un Excel."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import os
import tempfile

from ..utils import obtener_mensaje
from ..database import exportar_camaras_servicio
from ..registrador import (
    responder_registrando,
    registrar_conversacion,
    registrar_envio_email,
)
from ..correo import enviar_email
from .estado import UserState

logger = logging.getLogger(__name__)


async def iniciar_descarga_camaras(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Solicita al usuario el ID del servicio para generar el Excel."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_descarga_camaras.")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "descargar_camaras")
    context.user_data.clear()
    await responder_registrando(
        mensaje,
        user_id,
        "descargar_camaras",
        "Indicá el ID del servicio para obtener sus cámaras.",
        "descargar_camaras",
    )


async def enviar_camaras_servicio(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Genera y envía un Excel con las cámaras del servicio indicado."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.text:
        logger.warning("No se recibió ID de servicio en enviar_camaras_servicio.")
        return

    id_text = mensaje.text.strip()
    if not id_text.isdigit():
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            id_text,
            "El ID debe ser numérico.",
            "descargar_camaras",
        )
        return

    id_servicio = int(id_text)
    ruta = os.path.join(tempfile.gettempdir(), f"camaras_{mensaje.from_user.id}.xlsx")
    ok = exportar_camaras_servicio(id_servicio, ruta)
    if not ok or not os.path.exists(ruta):
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            id_text,
            "No hay cámaras registradas para ese servicio.",
            "descargar_camaras",
        )
        return

    try:
        from ..email_utils import generar_nombre_camaras

        nombre_archivo = generar_nombre_camaras(id_servicio) + ".xlsx"
        with open(ruta, "rb") as f:
            await mensaje.reply_document(f, filename=nombre_archivo)
        registrar_conversacion(
            mensaje.from_user.id,
            id_text,
            f"Documento {nombre_archivo} enviado",
            "descargar_camaras",
        )

        # Obtener destinatarios del cliente asociado al servicio
        from ..database import obtener_destinatarios_servicio

        destinatarios = obtener_destinatarios_servicio(id_servicio)
        if destinatarios:
            if enviar_email(
                destinatarios,
                "Listado de camaras",
                "Adjunto el Excel generado por SandyBot.",
                ruta,
                nombre_archivo,
            ):
                registrar_envio_email(
                    mensaje.from_user.id, destinatarios, nombre_archivo
                )
    except Exception as e:
        logger.error("Error al enviar listado de cámaras: %s", e)
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            id_text,
            f"Error al enviar el listado de cámaras: {e}",
            "descargar_camaras",
        )
    finally:
        UserState.set_mode(update.effective_user.id, "")
        context.user_data.clear()
        if os.path.exists(ruta):
            os.remove(ruta)
