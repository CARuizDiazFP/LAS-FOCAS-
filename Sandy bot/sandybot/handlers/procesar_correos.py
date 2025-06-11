"""Procesamiento masivo de correos .msg para registrar tareas."""

import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

try:
    import extract_msg
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "No se encontró la librería 'extract-msg'. Instalala para usar 'procesar_correos'."
    ) from exc

from ..utils import obtener_mensaje
from ..email_utils import procesar_correo_a_tarea, enviar_correo
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)


def _leer_msg(ruta: str) -> str:
    """Devuelve el asunto y cuerpo de un archivo MSG."""
    try:
        msg = extract_msg.Message(ruta)
        asunto = msg.subject or ""
        cuerpo = msg.body or ""
        if hasattr(msg, "close"):
            msg.close()
        return f"{asunto}\n{cuerpo}".strip()
    except Exception as exc:  # pragma: no cover - depende del archivo
        logger.error("Error leyendo MSG %s: %s", ruta, exc)
        return ""


async def procesar_correos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analiza uno o varios archivos `.msg` adjuntos y crea las tareas."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return

    user_id = update.effective_user.id

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

    docs = []
    if getattr(mensaje, "document", None):
        docs.append(mensaje.document)
    docs.extend(getattr(mensaje, "documents", []))
    if not docs:
        return
    first_name = getattr(docs[0], "file_name", "")

    tareas = []

    for doc in docs:
        archivo = await doc.get_file()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await archivo.download_to_drive(tmp.name)
            ruta = tmp.name
        try:
            contenido = _leer_msg(ruta)
            if not contenido:
                raise ValueError("Sin contenido")
            prompt = (
                "Extraé del siguiente correo los datos de la ventana de mantenimiento "
                "y devolvé solo un JSON con las claves 'inicio', 'fin', 'tipo', "
                "'afectacion' e 'ids' (lista de servicios).\n\n"
                f"Correo:\n{contenido}"
            )
            esquema = {
                "type": "object",
                "properties": {

        try:
            contenido = _leer_msg(ruta)
            if not contenido:
                raise ValueError("Sin contenido")
            tarea, cliente, ruta_msg = await procesar_correo_a_tarea(
                contenido, cliente_nombre, carrier_nombre
            )
        except Exception as e:  # pragma: no cover - manejo simple
            logger.error("Fallo procesando correo: %s", e)
            os.remove(ruta)
            continue
        os.remove(ruta)

        cuerpo = ""
        try:
            cuerpo = Path(ruta_msg).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
        enviar_correo(
            f"Aviso de tarea programada - {cliente.nombre}",
            cuerpo,
            cliente.id,
            carrier_nombre,
        )

        if ruta_msg.exists():
            with open(ruta_msg, "rb") as f:
                await mensaje.reply_document(f, filename=ruta_msg.name)
        tareas.append(str(tarea.id))

    if tareas:
        await responder_registrando(
            mensaje,
            user_id,
            first_name,
            f"Tareas registradas: {', '.join(tareas)}",
            "tareas",
        )

