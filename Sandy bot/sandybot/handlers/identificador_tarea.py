# + Nombre de archivo: identificador_tarea.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/identificador_tarea.py
# User-provided custom instructions
"""Flujo para identificar tareas programadas desde correos .MSG."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from ..registrador import responder_registrando
from .estado import UserState
from .procesar_correos import _leer_msg
from ..email_utils import procesar_correo_a_tarea

logger = logging.getLogger(__name__)


async def iniciar_identificador_tarea(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Solicita el correo .MSG a analizar."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_identificador_tarea")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "identificador_tarea")
    context.user_data.clear()
    await responder_registrando(
        mensaje,
        user_id,
        "identificador_tarea",
        "Adjuntá el correo .MSG con la tarea. "
        "En el texto indicá el nombre del cliente y opcionalmente el carrier.",
        "identificador_tarea",
    )


async def procesar_identificador_tarea(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Procesa el .MSG recibido y registra la tarea."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.document:
        logger.warning("No se recibió documento en procesar_identificador_tarea")
        return

    user_id = mensaje.from_user.id
    partes = (mensaje.text or "").split()
    if not partes:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.document.file_name,
            "Indicá cliente y opcionalmente carrier en el texto del mensaje.",
            "identificador_tarea",
        )
        return
    cliente = partes[0]
    carrier = partes[1] if len(partes) > 1 else None

    archivo = await mensaje.document.get_file()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        await archivo.download_to_drive(tmp.name)
        ruta = tmp.name

    try:
        contenido = _leer_msg(ruta)
        if not contenido:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.document.file_name,
                "Instalá la librería 'extract-msg' para leer archivos .MSG.",
                "identificador_tarea",
            )
            os.remove(ruta)
            return

        tarea, cliente_obj, ruta_msg, _ = await procesar_correo_a_tarea(
            contenido, cliente, carrier
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Fallo identificando tarea: %s", exc)
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.document.file_name,
            "No pude identificar la tarea en el correo.",
            "identificador_tarea",
        )
        os.remove(ruta)
        return
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)

    if ruta_msg.exists():
        with open(ruta_msg, "rb") as f:
            await mensaje.reply_document(f, filename=ruta_msg.name)
        os.remove(ruta_msg)

    await responder_registrando(
        mensaje,
        user_id,
        mensaje.document.file_name,
        f"Tarea {tarea.id} registrada para {cliente_obj.nombre}.",
        "identificador_tarea",
    )
    UserState.set_mode(user_id, "")
    context.user_data.clear()
