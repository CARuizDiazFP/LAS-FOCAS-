"""Módulo para generar informes de SLA."""
from __future__ import annotations

import os
import tempfile

import pandas as pd
from docx import Document
from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion


def generar_informe_sla(path_reclamos: str, path_servicios: str) -> str:
    """Genera un informe de SLA a partir de dos archivos Excel."""
    reclamos = pd.read_excel(path_reclamos)
    servicios = pd.read_excel(path_servicios)

    fecha = pd.to_datetime(reclamos.iloc[0].get("Fecha"))
    mes = fecha.strftime("%B")
    anio = fecha.strftime("%Y")

    doc = Document()
    doc.add_heading(f"Informe SLA {mes} {anio}", level=0)

    for _, servicio in servicios.iterrows():
        sid = servicio.get("ID Servicio")
        cliente = servicio.get("Cliente", "")
        doc.add_heading(f"Servicio {sid} - {cliente}", level=1)
        total = len(reclamos[reclamos.get("ID Servicio") == sid])
        doc.add_paragraph(f"Reclamos: {total}")

    nombre = f"InformeSLA{fecha.strftime('%m%y')}.docx"
    ruta = os.path.join(tempfile.gettempdir(), nombre)
    doc.save(ruta)
    return ruta


async def procesar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa los adjuntos y envía el informe de SLA generado."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
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

    ruta_doc = generar_informe_sla(tmp_paths[0], tmp_paths[1])

    with open(ruta_doc, "rb") as f:
        await mensaje.reply_document(f, filename=os.path.basename(ruta_doc))

    registrar_conversacion(
        update.effective_user.id,
        "informe_sla",
        f"Documento {os.path.basename(ruta_doc)} enviado",
        "informe_sla",
    )

    for p in tmp_paths:
        os.remove(p)
    # Nota: no eliminamos el DOCX para permitir verificarlo luego
    UserState.set_mode(update.effective_user.id, "")
