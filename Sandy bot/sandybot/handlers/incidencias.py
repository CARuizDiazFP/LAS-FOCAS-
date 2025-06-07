"""Manejadores para el análisis de incidencias."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import tempfile
import os
import subprocess
from docx import Document

from ..gpt_handler import gpt
from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)


def leer_documento(ruta: str) -> str:
    """Devuelve el texto de un .docx o .doc."""
    if ruta.lower().endswith(".docx"):
        doc = Document(ruta)
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    # Para archivos .doc se utiliza la herramienta `antiword`
    resultado = subprocess.run([
        "antiword",
        ruta,
    ], capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(resultado.stderr.strip() or "antiword falló")
    return resultado.stdout

async def iniciar_incidencias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia el flujo solicitando documentos .docx o .doc."""
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
        "Enviá el documento .docx o .doc con las incidencias para procesar.",
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
    nombre = documento.file_name.lower()
    if not (nombre.endswith(".docx") or nombre.endswith(".doc")):
        await responder_registrando(
            mensaje,
            user_id,
            documento.file_name,
            "Solo acepto archivos .docx o .doc para analizar incidencias.",
            "incidencias",
        )
        return

    archivo = await documento.get_file()
    sufijo = ".docx" if nombre.endswith(".docx") else ".doc"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        await archivo.download_to_drive(tmp.name)
        ruta_doc = tmp.name

    try:
        texto = leer_documento(ruta_doc)
    except Exception as e:
        logger.error("Error leyendo documento: %s", e)
        await responder_registrando(
            mensaje,
            user_id,
            documento.file_name,
            f"No pude leer el documento: {e}",
            "incidencias",
        )
        os.remove(ruta_doc)
        return

    # Guardar ruta y texto para procesar varios documentos a la vez
    context.user_data.setdefault("docs", []).append(ruta_doc)
    if "contexto" in nombre:
        context.user_data.setdefault("contexto", []).append(texto)
    else:
        context.user_data.setdefault("principal", []).append(texto)

    texto_principal = "\n".join(context.user_data.get("principal", []))
    if context.user_data.get("contexto"):
        texto_total = texto_principal + "\n" + "\n".join(context.user_data["contexto"])
    else:
        texto_total = texto_principal

    try:
        datos = await gpt.analizar_incidencias(texto_total)
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
        for ruta in context.user_data.get("docs", []):
            try:
                os.remove(ruta)
            except OSError:
                pass
        context.user_data.clear()

    lineas = [f"{d.get('fecha')}: {d.get('evento')}" for d in datos]
    respuesta = "Cronología de incidencias:\n" + "\n".join(lineas)
    await responder_registrando(
        mensaje,
        user_id,
        documento.file_name,
        respuesta,
        "incidencias",
    )
