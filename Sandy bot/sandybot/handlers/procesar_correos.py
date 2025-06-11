"""Procesamiento masivo de correos .msg para registrar tareas."""

from __future__ import annotations

import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

try:
    import extract_msg
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "No se encontró la librería 'extract-msg'. Instalala para usar /procesar_correos."
    ) from exc

from ..utils import obtener_mensaje
from ..email_utils import procesar_correo_a_tarea, enviar_correo
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)


# ────────────────────────── UTILIDAD LOCAL ──────────────────────────
def _leer_msg(ruta: str) -> str:
    """Devuelve el `asunto + cuerpo` de un archivo MSG."""
    try:
        msg = extract_msg.Message(ruta)
        asunto = msg.subject or ""
        cuerpo = msg.body or ""
        if hasattr(msg, "close"):
            msg.close()
        return f"{asunto}\n{cuerpo}".strip()
    except Exception as exc:  # pragma: no cover
        logger.error("Error leyendo MSG %s: %s", ruta, exc)
        return ""


# ────────────────────────── HANDLER PRINCIPAL ───────────────────────
async def procesar_correos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analiza uno o varios `.msg` adjuntos y registra las tareas encontradas."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return

    user_id = update.effective_user.id

    # Parámetros: /procesar_correos <cliente> [carrier]
    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or getattr(mensaje.document, "file_name", ""),
            "Usá: /procesar_correos <cliente> [carrier] y adjuntá los archivos.",
            "tareas",
        )
        return

    cliente_nombre = context.args[0]
    carrier_nombre = context.args[1] if len(context.args) > 1 else None

    # Recolectamos documentos adjuntos
    docs: list = []
    if getattr(mensaje, "document", None):
        docs.append(mensaje.document)
    docs.extend(getattr(mensaje, "documents", []))
    if not docs:
        return
    first_name = getattr(docs[0], "file_name", "")

    tareas: list[str] = []

    for doc in docs:
        archivo = await doc.get_file()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await archivo.download_to_drive(tmp.name)
            ruta_tmp = tmp.name

        try:
            contenido = _leer_msg(ruta_tmp)
            if not contenido:
                raise ValueError("Sin contenido")

            # Procesa correo → registra tarea y genera .msg
            tarea, cliente, ruta_msg, cuerpo = await procesar_correo_a_tarea(
                contenido, cliente_nombre, carrier_nombre
            )
        except Exception as e:  # pragma: no cover
            logger.error("Fallo procesando correo %s: %s", doc.file_name, e)
            os.remove(ruta_tmp)
            continue
        finally:
            # Eliminamos el .msg original descargado
            if os.path.exists(ruta_tmp):
                os.remove(ruta_tmp)

        # Envía aviso a destinatarios del cliente
        enviar_correo(
            f"Aviso de tarea programada - {cliente.nombre}",
            cuerpo,
            cliente.id,
            carrier_nombre,
        )

        # Adjunta el .msg generado al chat
        if ruta_msg.exists():
            with open(ruta_msg, "rb") as f:
                await mensaje.reply_document(f, filename=ruta_msg.name)

        tareas.append(str(tarea.id))

    # Resumen final al usuario
    if tareas:
        await responder_registrando(
            mensaje,
            user_id,
            first_name,
            f"Tareas registradas: {', '.join(tareas)}",
            "tareas",
        )
