"""Manejadores para el análisis de incidencias."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import tempfile
import os
from docx import Document

from ..gpt_handler import gpt
from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)

async def iniciar_incidencias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia el flujo de análisis de incidencias solicitando el .docx."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_incidencias")
        return
    user_id = update.effective_user.id
    UserState.set_mode(user_id, "incidencias")
    context.user_data.clear()
    await responder_registrando(
        mensaje,
        user_id,
        "analizar_incidencias",
        "Enviá el documento .docx con las incidencias para procesar.",
        "incidencias",
    )

async def procesar_incidencias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa el documento de incidencias proporcionado por el usuario."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.document:
        logger.warning("No se recibió documento en procesar_incidencias")
        return

    user_id = mensaje.from_user.id
    documento = mensaje.document
    if not documento.file_name.endswith(".docx"):
        await responder_registrando(
            mensaje,
            user_id,
            documento.file_name,
            "Solo acepto archivos .docx para analizar incidencias.",
            "incidencias",
        )
        return

    archivo = await documento.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        await archivo.download_to_drive(tmp.name)
        ruta_docx = tmp.name

    try:
        doc = Document(ruta_docx)
        texto = "\n".join(p.text for p in doc.paragraphs if p.text)
    except Exception as e:
        logger.error("Error leyendo docx: %s", e)
        await responder_registrando(
            mensaje,
            user_id,
            documento.file_name,
            f"No pude leer el documento: {e}",
            "incidencias",
        )
        return

    try:
        datos = await gpt.analizar_incidencias(texto)
        if not datos:
            raise ValueError("JSON inválido")
    except Exception as e:
        logger.error("Fallo analizando incidencias: %s", e)
        await responder_registrando(
            mensaje,
            user_id,
            documento.file_name,
            "Hubo un problema analizando las incidencias.",
            "incidencias",
        )
        return
    finally:
        os.remove(ruta_docx)

    lineas = [f"{d.get('fecha')}: {d.get('evento')}" for d in datos]
    respuesta = "Cronología de incidencias:\n" + "\n".join(lineas)
    await responder_registrando(
        mensaje,
        user_id,
        documento.file_name,
        respuesta,
        "incidencias",
    )
