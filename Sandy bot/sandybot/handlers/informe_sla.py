"""Handler para generar informes de SLA."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion

import pandas as pd
from docx import Document
from telegram import Update
from telegram.ext import ContextTypes
from sandybot.config import config
# Plantilla de Word definida en configuración
RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH

logger = logging.getLogger(__name__)


# ────────────────────────── FLUJO DE INICIO ──────────────────────────
async def iniciar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pone al usuario en modo *informe_sla* y pide los dos Excel."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_informe_sla")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "informe_sla")
    context.user_data.clear()
    context.user_data["archivos"] = []

    await responder_registrando(
        mensaje,
        user_id,
        "informe_sla",
        "Enviá el Excel de **reclamos** y luego el de **servicios** para generar el informe.",
        "informe_sla",
    )


# ────────────────────────── FLUJO DE PROCESO ─────────────────────────
async def procesar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe los archivos de reclamos y servicios y genera el informe."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en procesar_informe_sla")
        return

    docs = []
    if getattr(mensaje, "document", None):
        docs.append(mensaje.document)
    docs.extend(getattr(mensaje, "documents", []))

    if len(docs) < 2:
        await responder_registrando(
            mensaje,
            update.effective_user.id,
            getattr(docs[0], "file_name", mensaje.text or ""),
            "Adjuntá los Excel de reclamos y servicios.",
            "informe_sla",
        )
        return

    tmp_paths: list[str] = []
    for doc in docs[:2]:
        archivo = await doc.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            await archivo.download_to_drive(tmp.name)
            tmp_paths.append(tmp.name)

    ruta_final = _generar_documento_sla(tmp_paths[0], tmp_paths[1])

    with open(ruta_final, "rb") as f:
        await mensaje.reply_document(f, filename=os.path.basename(ruta_final))

    registrar_conversacion(
        update.effective_user.id,
        "informe_sla",
        f"Documento {os.path.basename(ruta_final)} enviado",
        "informe_sla",
    )

    for p in tmp_paths:
        os.remove(p)
    UserState.set_mode(update.effective_user.id, "")


# ─────────────────────── FUNCIÓN GENERADORA DE WORD ───────────────────
def _generar_documento_sla(reclamos_xlsx: str, servicios_xlsx: str) -> str:
    """Combina reclamos y servicios en un documento Word."""
    reclamos = pd.read_excel(reclamos_xlsx)
    servicios = pd.read_excel(servicios_xlsx)

    fecha = pd.to_datetime(reclamos.iloc[0].get("Fecha"))
    mes = fecha.strftime("%B")
    anio = fecha.strftime("%Y")

    if RUTA_PLANTILLA and os.path.exists(RUTA_PLANTILLA):
        doc = Document(RUTA_PLANTILLA)
    else:
        doc = Document()

    doc.add_heading(f"Informe SLA {mes} {anio}", level=0)

    for _, servicio in servicios.iterrows():
        sid = servicio.get("ID Servicio") or servicio.get("Servicio")
        cliente = servicio.get("Cliente", "")
        doc.add_heading(f"Servicio {sid} - {cliente}", level=1)
        total = len(reclamos[reclamos.get("ID Servicio", reclamos.get("Servicio")) == sid])
        doc.add_paragraph(f"Reclamos: {total}")

    nombre_arch = "InformeSLA.docx"
    ruta = os.path.join(tempfile.gettempdir(), nombre_arch)
    doc.save(ruta)
    return ruta
