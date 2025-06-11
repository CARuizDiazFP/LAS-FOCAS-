"""Handler para generar informes de SLA."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
from docx import Document
from telegram import Update
from telegram.ext import ContextTypes

from sandybot.config import config
from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion

# Plantilla de Word definida en la configuración
RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH

logger = logging.getLogger(__name__)


# ────────────────────────── FLUJO DE INICIO ──────────────────────────
async def iniciar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pone al usuario en modo *informe_sla* y solicita los dos archivos Excel."""
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
    """Recibe los archivos de reclamos y servicios y genera el informe SLA."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en procesar_informe_sla")
        return

    docs: list = []
    if getattr(mensaje, "document", None):
        docs.append(mensaje.document)
    docs.extend(getattr(mensaje, "documents", []))

    # Debemos recibir al menos dos Excel
    if len(docs) < 2:
        await responder_registrando(
            mensaje,
            update.effective_user.id,
            getattr(docs[0], "file_name", mensaje.text or ""),
            "Adjuntá los Excel de reclamos y servicios.",
            "informe_sla",
        )
        return

    # Descarga temporal de ambos archivos
    tmp_paths: list[str] = []
    for doc in docs[:2]:
        archivo = await doc.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            await archivo.download_to_drive(tmp.name)
            tmp_paths.append(tmp.name)

    try:
        # Generar documento Word
        ruta_final = _generar_documento_sla(tmp_paths[0], tmp_paths[1])

        with open(ruta_final, "rb") as f:
            await mensaje.reply_document(f, filename=os.path.basename(ruta_final))

        registrar_conversacion(
            update.effective_user.id,
            "informe_sla",
            f"Documento {os.path.basename(ruta_final)} enviado",
            "informe_sla",
        )
    except ValueError as e:
        logger.error("Error generando informe SLA: %s", e)
        await responder_registrando(
            mensaje,
            update.effective_user.id,
            os.path.basename(tmp_paths[0]),
            str(e),
            "informe_sla",
        )
    except Exception as e:  # pragma: no cover
        logger.error("Error generando informe SLA: %s", e)
        await responder_registrando(
            mensaje,
            update.effective_user.id,
            os.path.basename(tmp_paths[0]),
            "💥 Algo falló generando el informe de SLA.",
            "informe_sla",
        )
    finally:
        # Limpieza de archivos temporales y estado
        for p in tmp_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        UserState.set_mode(update.effective_user.id, "")


# ─────────────────────── FUNCIÓN GENERADORA DE WORD ───────────────────
def _generar_documento_sla(reclamos_xlsx: str, servicios_xlsx: str) -> str:
    """Combina reclamos y servicios en un documento Word usando la plantilla (si existe)."""
    reclamos_df = pd.read_excel(reclamos_xlsx)
    servicios_df = pd.read_excel(servicios_xlsx)

    # Normaliza nombres de columna
    if "Servicio" not in reclamos_df.columns:
        reclamos_df.rename(columns={reclamos_df.columns[0]: "Servicio"}, inplace=True)
    if "Servicio" not in servicios_df.columns:
        servicios_df.rename(columns={servicios_df.columns[0]: "Servicio"}, inplace=True)

    # Título: mes y año del primer reclamo
    try:
        fecha = pd.to_datetime(reclamos_df.iloc[0].get("Fecha"))
    except Exception:
        fecha = pd.Timestamp.today()
    mes = fecha.strftime("%B")
    anio = fecha.strftime("%Y")

    # Conteo de reclamos por servicio
    resumen = reclamos_df.groupby("Servicio").size().reset_index(name="Reclamos")
    df = servicios_df.merge(resumen, on="Servicio", how="left")
    df["Reclamos"] = df["Reclamos"].fillna(0).astype(int)

    # Documento base
    if not (RUTA_PLANTILLA and os.path.exists(RUTA_PLANTILLA)):
        logger.error("Plantilla de SLA no encontrada: %s", RUTA_PLANTILLA)
        raise ValueError("Plantilla de SLA no encontrada")
    doc = Document(RUTA_PLANTILLA)

    doc.add_heading(f"Informe SLA {mes} {anio}", level=0)

    # Tabla de resumen
    tabla = doc.add_table(rows=1, cols=2, style="Table Grid")
    hdr = tabla.rows[0].cells
    hdr[0].text = "Servicio"
    hdr[1].text = "Reclamos"

    for _, fila in df.iterrows():
        row = tabla.add_row().cells
        row[0].text = str(fila["Servicio"])
        row[1].text = str(fila["Reclamos"])

    # Guardado temporal
    nombre_arch = "InformeSLA.docx"
    ruta_salida = os.path.join(tempfile.gettempdir(), nombre_arch)
    doc.save(ruta_salida)
    return ruta_salida
