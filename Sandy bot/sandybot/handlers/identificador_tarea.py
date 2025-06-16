# Nombre de archivo: identificador_tarea.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/identificador_tarea.py
# User-provided custom instructions
"""Flujo para identificar tareas programadas desde correos .MSG."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from ..email_utils import procesar_correo_a_tarea
from ..registrador import responder_registrando
from ..utils import obtener_mensaje
from .estado import UserState
from .procesar_correos import _leer_msg

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
        "📎 Adjuntá el archivo *.MSG* del mantenimiento.\n"
        "No hace falta escribir nada más, yo me encargo del resto 😉",
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
    cliente = partes[0] if partes else "METROTEL"
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

        tarea, ids_pendientes = await procesar_correo_a_tarea(
            contenido, cliente, carrier, generar_msg=False
        )
    except ValueError as exc:
        logger.error("Fallo identificando tarea: %s", exc)
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.document.file_name,
            "No pude identificar la tarea en el correo. Podés cargarla "
            "manualmente con /ingresar_tarea",
            "identificador_tarea",
        )
        os.remove(ruta)
        return
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

        for token in ids_faltantes:
            crear_servicio_pendiente(token, tarea.id)
            logger.info("ServicioPendiente creado: %s", token)

        # ── Detalle de la tarea registrada ──────────────────────────
        detalle = (
            f"✅ *Tarea Registrada ID: {tarea.id}*\n"
            f"• Carrier : {tarea.carrier.nombre if tarea.carrier_id else 'Sin carrier'}\n"
            f"• Tipo    : {tarea.tipo_tarea}\n"
            f"• Inicio  : {tarea.fecha_inicio}\n"
            f"• Fin     : {tarea.fecha_fin}\n"
        )
        if tarea.tiempo_afectacion:
            detalle += f"• Afectación: {tarea.tiempo_afectacion}\n"
        if tarea.descripcion:
            detalle += f"• Descripción: {tarea.descripcion}\n"
        if ids_pendientes:
            detalle += f"⚠️ *Servicios pendientes*: {', '.join(ids_pendientes)}"

        await update.message.reply_text(detalle, parse_mode="Markdown")
        UserState.set_mode(user_id, "")
        context.user_data.clear()

