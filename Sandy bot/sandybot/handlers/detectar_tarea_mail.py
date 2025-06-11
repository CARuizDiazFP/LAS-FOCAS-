"""Detección automática de tareas programadas desde correos."""

import logging
import os
import tempfile
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from ..email_utils import procesar_correo_a_tarea
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)


async def detectar_tarea_mail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa un correo enviado por Telegram y registra la tarea."""

    mensaje = obtener_mensaje(update)
    if not mensaje:
        return

    user_id = update.effective_user.id

    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "detectar_tarea_mail",
            "Usá: /detectar_tarea <cliente> y pegá el correo o adjuntalo como archivo.",
            "tareas",
        )
        return

    cliente_nombre = context.args[0]; carrier_nombre = context.args[1] if len(context.args) > 1 else None

    contenido = ""
    if mensaje.document:
        archivo = await mensaje.document.get_file()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await archivo.download_to_drive(tmp.name)
            ruta = tmp.name
        try:
            contenido = Path(ruta).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error("Error leyendo adjunto: %s", e)
            os.remove(ruta)
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.document.file_name,
                "No pude leer el archivo adjunto.",
                "tareas",
            )
            return
        finally:
            os.remove(ruta)
    else:
        if len(context.args) > 1:
            partes = mensaje.text.split(maxsplit=3)
            indice_cuerpo = 3
        else:
            partes = mensaje.text.split(maxsplit=2)
            indice_cuerpo = 2

        if len(partes) <= indice_cuerpo:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text or "detectar_tarea_mail",
                "Pegá el correo completo después del nombre del cliente.",
                "tareas",
            )
            return

        contenido = partes[indice_cuerpo]

    try:
        tarea, cliente, ruta, _ = await procesar_correo_a_tarea(

            contenido,
            cliente_nombre,
            carrier_nombre,

        )
    except Exception as e:
        logger.error("Fallo detectando tarea: %s", e)
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or getattr(mensaje.document, "file_name", ""),
            "No pude identificar la tarea en el correo.",
            "tareas",
        )
        return

    if ruta.exists():
        with open(ruta, "rb") as f:
            await mensaje.reply_document(f, filename=ruta.name)

    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or getattr(mensaje.document, "file_name", ""),
        f"Tarea {tarea.id} registrada.",
        "tareas",
    )
