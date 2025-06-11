
"""Handler para generar informes de SLA."""

from telegram import Update
from telegram.ext import ContextTypes

import logging
import tempfile
import os
import pandas as pd
from docx import Document

from sandybot.config import config
from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion

# Plantilla de Word definida en configuración
RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH

logger = logging.getLogger(__name__)


async def iniciar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia el flujo para generar el informe de SLA.

    1️⃣ Pone al usuario en modo *informe_sla*.  
    2️⃣ Limpia `context.user_data` para recibir los dos Excel.  
    3️⃣ Envía mensaje de instrucciones.
    """
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
        "Enviá el Excel de reclamos y luego el de servicios para generar el informe.",
        "informe_sla",
    )


async def procesar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe los archivos de reclamos y servicios y genera el informe."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.document:
        logger.warning("No se recibió documento en procesar_informe_sla")
        return

    user_id = mensaje.from_user.id
    doc = mensaje.document

    # ✅ Solo Excel
    if not doc.file_name.endswith(".xlsx"):
        await responder_registrando(
            mensaje,
            user_id,
            doc.file_name,
            "🙄 Solo acepto archivos Excel (.xlsx).",
            "informe_sla",
        )
        return

    # ⬇️ Descargamos y guardamos en user_data
    archivo = await doc.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        await archivo.download_to_drive(tmp.name)
        context.user_data.setdefault("archivos", []).append(tmp.name)

    # Esperamos los dos Excels
    if len(context.user_data["archivos"]) < 2:
        await responder_registrando(
            mensaje,
            user_id,
            doc.file_name,
            "Archivo recibido. Enviá el Excel restante para continuar.",
            "informe_sla",
        )
        return

    reclamos_path, servicios_path = context.user_data["archivos"][:2]

    try:
        ruta_salida = _generar_documento_sla(reclamos_path, servicios_path)
        nombre_final = os.path.basename(ruta_salida)

        with open(ruta_salida, "rb") as docx_file:
            await mensaje.reply_document(document=docx_file, filename=nombre_final)

        registrar_conversacion(
            user_id,
            doc.file_name,
            f"Documento {nombre_final} enviado",
            "informe_sla",
        )
    except Exception as e:  # pragma: no cover
        logger.error("Error generando informe SLA: %s", e)
        await responder_registrando(
            mensaje,
            user_id,
            doc.file_name,
            "💥 Algo falló generando el informe de SLA.",
            "informe_sla",
        )
    finally:
        # Limpieza de temporales y estado
        for ruta in context.user_data.get("archivos", []):
            try:
                os.remove(ruta)
            except OSError:
                pass
        if "ruta_salida" in locals() and os.path.exists(ruta_salida):
            os.remove(ruta_salida)

        context.user_data.clear()
        UserState.set_mode(user_id, "")


def _generar_documento_sla(reclamos_xlsx: str, servicios_xlsx: str) -> str:
    """Combina reclamos y servicios en un documento Word usando la plantilla."""
    reclamos_df = pd.read_excel(reclamos_xlsx)
    servicios_df = pd.read_excel(servicios_xlsx)

    if "Servicio" not in reclamos_df.columns:
        reclamos_df.rename(columns={reclamos_df.columns[0]: "Servicio"}, inplace=True)
    if "Servicio" not in servicios_df.columns:
        servicios_df.rename(columns={servicios_df.columns[0]: "Servicio"}, inplace=True)

    resumen = reclamos_df.groupby("Servicio").size().reset_index(name="Reclamos")
    df = servicios_df.merge(resumen, on="Servicio", how="left")
    df["Reclamos"] = df["Reclamos"].fillna(0).astype(int)

    doc = Document(RUTA_PLANTILLA)
    tabla = doc.add_table(rows=1, cols=2, style="Table Grid")
    hdr = tabla.rows[0].cells
    hdr[0].text = "Servicio"
    hdr[1].text = "Reclamos"

    for _, fila in df.iterrows():
        row = tabla.add_row().cells
        row[0].text = str(fila["Servicio"])
        row[1].text = str(fila["Reclamos"])

    nombre_archivo = "InformeSLA.docx"
    ruta_salida = os.path.join(tempfile.gettempdir(), nombre_archivo)
    doc.save(ruta_salida)
    return ruta_salida

