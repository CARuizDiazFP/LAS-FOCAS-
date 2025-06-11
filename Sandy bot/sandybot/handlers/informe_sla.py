"""Handler para generar informes de SLA."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

import pandas as pd
from docx import Document
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    context.user_data["archivos"] = [None, None]  # [reclamos, servicios]

    await responder_registrando(
        mensaje,
        user_id,
        "informe_sla",
        "Enviá el Excel de **reclamos** y luego el de **servicios** para generar el informe.",
        "informe_sla",
    )


# ────────────────────────── FLUJO DE PROCESO ─────────────────────────
async def procesar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestiona la generación del informe SLA: carga 2 Excel → botón Procesar → genera Word."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en procesar_informe_sla")
        return

    user_id = update.effective_user.id
    archivos = context.user_data.setdefault("archivos", [None, None])

    # ───── Callback «Procesar informe» ─────
    if update.callback_query and update.callback_query.data == "sla_procesar":
        reclamos_xlsx, servicios_xlsx = archivos
        try:
            ruta_final = _generar_documento_sla(reclamos_xlsx, servicios_xlsx)
            with open(ruta_final, "rb") as f:
                await update.callback_query.message.reply_document(
                    f, filename=os.path.basename(ruta_final)
                )
            registrar_conversacion(
                user_id,
                "informe_sla",
                f"Documento {os.path.basename(ruta_final)} enviado",
                "informe_sla",
            )
        except Exception as e:  # pragma: no cover
            logger.error("Error generando informe SLA: %s", e)
            await update.callback_query.message.reply_text(
                "💥 Algo falló generando el informe de SLA."
            )
        finally:
            for p in archivos:
                try:
                    os.remove(p)
                except OSError:
                    pass
            context.user_data.clear()
            UserState.set_mode(user_id, "")
        return

    # ───── Recepción de archivos Excel ─────
    docs: list = []
    if getattr(mensaje, "document", None):
        docs.append(mensaje.document)
    docs.extend(getattr(mensaje, "documents", []))

    if docs:
        for doc in docs:
            archivo = await doc.get_file()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                await archivo.download_to_drive(tmp.name)
                nombre = doc.file_name.lower()
                if "recl" in nombre and archivos[0] is None:
                    archivos[0] = tmp.name
                elif "serv" in nombre and archivos[1] is None:
                    archivos[1] = tmp.name
                elif archivos[0] is None:
                    archivos[0] = tmp.name
                else:
                    archivos[1] = tmp.name

        if None in archivos:
            falta = "reclamos" if archivos[0] is None else "servicios"
            await responder_registrando(
                mensaje,
                user_id,
                docs[-1].file_name,
                f"Archivo guardado. Falta el Excel de {falta}.",
                "informe_sla",
            )
            return

        # Ambos archivos listos: mostrar botón Procesar
        try:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Procesar informe 🚀", callback_data="sla_procesar")]]
            )
        except Exception:  # pragma: no cover
            class _Btn:
                def __init__(self, text: str, callback_data: str | None = None):
                    self.text = text
                    self.callback_data = callback_data

            class _Mk:
                def __init__(self, keyboard):
                    self.inline_keyboard = keyboard

            keyboard = _Mk([[_Btn("Procesar informe 🚀", callback_data="sla_procesar")]])
        await responder_registrando(
            mensaje,
            user_id,
            docs[-1].file_name,
            "Archivos cargados. Presioná *Procesar informe*.",
            "informe_sla",
            reply_markup=keyboard,
        )
        return

    # Si llegó aquí sin adjuntos ni callback, se recuerda al usuario qué hacer
    await responder_registrando(
        mensaje,
        user_id,
        getattr(mensaje, "text", ""),
        "Adjuntá los archivos de reclamos y servicios para comenzar.",
        "informe_sla",
    )


# ─────────────────────── FUNCIÓN GENERADORA DE WORD ───────────────────
def _generar_documento_sla(
    reclamos_xlsx: str,
    servicios_xlsx: str,
    eventos: Optional[str] = "",
    conclusion: Optional[str] = "",
    propuesta: Optional[str] = "",
    exportar_pdf: bool = False,
) -> str:
    """Combina datos y genera el documento SLA usando la plantilla personalizada."""
    reclamos_df = pd.read_excel(reclamos_xlsx)
    servicios_df = pd.read_excel(servicios_xlsx)

    # Normaliza nombres de columna
    if "Servicio" not in reclamos_df.columns:
        reclamos_df.rename(columns={reclamos_df.columns[0]: "Servicio"}, inplace=True)
    if "Servicio" not in servicios_df.columns:
        servicios_df.rename(columns={servicios_df.columns[0]: "Servicio"}, inplace=True)

    # Título Mes/Año
    try:
        fecha = pd.to_datetime(reclamos_df.iloc[0].get("Fecha"))
        if pd.isna(fecha):
            raise ValueError
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

    # Insertar textos personalizados (si se pasan)
    etiquetas = {
        "Eventos sucedidos de mayor impacto en SLA:": eventos,
        "Conclusión:": conclusion,
        "Propuesta de mejora:": propuesta,
    }
    encontrados = set()
    for p in doc.paragraphs:
        pref = p.text.strip()
        for etiqueta, contenido in etiquetas.items():
            if pref.startswith(etiqueta):
                p.text = f"{etiqueta} {contenido}"
                encontrados.add(etiqueta)
                break
    for etiqueta, contenido in etiquetas.items():
        if etiqueta not in encontrados and contenido:
            doc.add_paragraph(f"{etiqueta} {contenido}")

    # Guardado temporal
    nombre_archivo = "InformeSLA.docx"
    ruta_salida = os.path.join(tempfile.gettempdir(), nombre_archivo)
    doc.save(ruta_salida)

    if exportar_pdf and os.name == "nt":
        try:
            from win32com.client import Dispatch

            word = Dispatch("Word.Application")
            doc_com = word.Documents.Open(ruta_salida)
            ruta_pdf = os.path.splitext(ruta_salida)[0] + ".pdf"
            doc_com.SaveAs(ruta_pdf, FileFormat=17)
            doc_com.Close()
            word.Quit()
            ruta_salida = ruta_pdf
        except Exception as e:  # pragma: no cover
            logger.error("Error convirtiendo a PDF: %s", e)

    return ruta_salida
