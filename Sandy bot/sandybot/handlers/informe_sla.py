# + Nombre de archivo: informe_sla.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/informe_sla.py
# User-provided custom instructions
"""Handler para generar informes de SLA."""

from __future__ import annotations

import logging
import os
import tempfile
import locale
from types import SimpleNamespace
from typing import Optional

import pandas as pd
from docx import Document
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Dependencia opcional para exportar PDF en Windows
try:  # pragma: no cover
    import win32com.client as win32  # type: ignore
except Exception:  # pragma: no cover
    win32 = None

from sandybot.config import config
from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion

# Plantilla de Word definida en la configuración
RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH

logger = logging.getLogger(__name__)


# ───────────────────────── FLUJO DE INICIO ──────────────────────────
async def iniciar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Activa modo *informe_sla* y solicita los dos Excel."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_informe_sla")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "informe_sla")
    context.user_data.clear()
    context.user_data["archivos"] = [None, None]           # [reclamos, servicios]

    # Botón para actualizar plantilla
    try:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Actualizar plantilla", callback_data="sla_cambiar_plantilla")]]
        )
    except Exception:  # fallback para stubs
        btn = SimpleNamespace(text="Actualizar plantilla", callback_data="sla_cambiar_plantilla")
        kb = SimpleNamespace(inline_keyboard=[[btn]])

    await responder_registrando(
        mensaje,
        user_id,
        "informe_sla",
        "Enviá el Excel de **reclamos** y luego el de **servicios** para generar el informe.",
        "informe_sla",
        reply_markup=kb,
    )


# ───────────────────────── FLUJO PRINCIPAL ──────────────────────────
async def procesar_informe_sla(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    exportar_pdf: bool = False,
) -> None:
    """Carga Excel -→ muestra opciones -→ genera Word o PDF."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en procesar_informe_sla")
        return

    user_id = update.effective_user.id
    archivos = context.user_data.setdefault("archivos", [None, None])

    # 1) Callback: cambiar plantilla
    if update.callback_query and update.callback_query.data == "sla_cambiar_plantilla":
        context.user_data["cambiar_plantilla"] = True
        await update.callback_query.message.reply_text("Adjuntá la nueva plantilla .docx.")
        return

    # 2) Guardar plantilla nueva
    if context.user_data.get("cambiar_plantilla"):
        if getattr(mensaje, "document", None):
            await actualizar_plantilla_sla(mensaje, context)
        else:
            await responder_registrando(
                mensaje, user_id, getattr(mensaje, "text", ""),
                "Adjuntá el .docx para actualizar la plantilla.", "informe_sla",
            )
        return

    # 3) Callback: procesar informe (Word o PDF)
    if update.callback_query and update.callback_query.data in {"sla_procesar", "sla_pdf"}:
        reclamos_xlsx, servicios_xlsx = archivos
        try:
            ruta_final = _generar_documento_sla(
                reclamos_xlsx,
                servicios_xlsx,
                exportar_pdf=exportar_pdf or update.callback_query.data == "sla_pdf",
            )
            with open(ruta_final, "rb") as f:
                await update.callback_query.message.reply_document(f, filename=os.path.basename(ruta_final))
            os.remove(ruta_final)
            registrar_conversacion(
                user_id, "informe_sla", f"Documento {os.path.basename(ruta_final)} enviado", "informe_sla"
            )
        except Exception as e:  # pragma: no cover
            logger.error("Error generando SLA: %s", e)
            await update.callback_query.message.reply_text("💥 Algo falló generando el informe de SLA.")
        finally:
            for p in archivos:
                try:
                    os.remove(p)
                except OSError:
                    pass
            context.user_data.clear()
            UserState.set_mode(user_id, "")
        return

    # 4) Recepción de archivos Excel
    docs = []
    for d in (getattr(mensaje, "document", None), *getattr(mensaje, "documents", [])):
        if d and d not in docs:
            docs.append(d)
    if docs:
        for doc in docs:
            f = await doc.get_file()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                await f.download_to_drive(tmp.name)
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
                mensaje, user_id, docs[-1].file_name,
                f"Archivo guardado. Falta el Excel de {falta}.", "informe_sla",
            )
            return

        # Botones procesar Word / PDF
        try:
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Procesar informe 🚀", callback_data="sla_procesar"),
                     InlineKeyboardButton("Exportar a PDF", callback_data="sla_pdf")]
                ]
            )
        except Exception:  # fallback stubs
            procesar = SimpleNamespace(text="Procesar informe 🚀", callback_data="sla_procesar")
            pdf = SimpleNamespace(text="Exportar a PDF", callback_data="sla_pdf")
            kb = SimpleNamespace(inline_keyboard=[[procesar, pdf]])

        await responder_registrando(
            mensaje, user_id, docs[-1].file_name,
            "Archivos cargados. Elegí una opción.", "informe_sla",
            reply_markup=kb,
        )
        return

    # 5) Ningún adjunto ni callback
    await responder_registrando(
        mensaje, user_id, getattr(mensaje, "text", ""),
        "Adjuntá los Excel de reclamos y servicios para comenzar.", "informe_sla",
    )


# ──────────────────── ACTUALIZAR PLANTILLA SLA ───────────────────────
async def actualizar_plantilla_sla(mensaje, context):
    user_id = mensaje.from_user.id
    archivo = mensaje.document
    if not archivo.file_name.lower().endswith(".docx"):
        await responder_registrando(mensaje, user_id, archivo.file_name, "El archivo debe ser .docx.", "informe_sla")
        return
    try:
        f = await archivo.get_file()
        os.makedirs(os.path.dirname(RUTA_PLANTILLA), exist_ok=True)
        await f.download_to_drive(RUTA_PLANTILLA)
        texto = "Plantilla de SLA actualizada."
        context.user_data.pop("cambiar_plantilla", None)
    except Exception as exc:  # pragma: no cover
        logger.error("Error guardando plantilla SLA: %s", exc)
        texto = "No se pudo guardar la plantilla."

    await responder_registrando(mensaje, user_id, archivo.file_name, texto, "informe_sla")


# ────────────────── GENERADOR DE DOCUMENTO SLA ───────────────────────
def _generar_documento_sla(
    reclamos_xlsx: str,
    servicios_xlsx: str,
    eventos: Optional[str] = "",
    conclusion: Optional[str] = "",
    propuesta: Optional[str] = "",
    *,
    exportar_pdf: bool = False,
) -> str:
    """Genera el documento SLA; si `exportar_pdf` es True intenta producir PDF."""
    reclamos_df = pd.read_excel(reclamos_xlsx)
    servicios_df = pd.read_excel(servicios_xlsx)

    # Columnas opcionales
    extra_cols = [c for c in ("SLA Entregado", "Dirección", "Horas Netas Reclamo") if c in servicios_df]
    faltantes = {"SLA Entregado", "Dirección", "Horas Netas Reclamo"} - set(servicios_df)
    if faltantes:
        logger.warning("Faltan columnas en servicios.xlsx: %s", ", ".join(sorted(faltantes)))


    # Formatea "Horas Netas Reclamo" si tiene valores numéricos
    if "Horas Netas Reclamo" in servicios_df.columns:
        def _fmt_horas(valor: object) -> object:
            if pd.isna(valor) or not any(ch.isdigit() for ch in str(valor)):
                return valor
            try:
                td = pd.to_timedelta(valor)
            except Exception:
                try:
                    td = pd.to_timedelta(float(str(valor).replace(",", ".")), unit="h")
                except Exception:
                    return valor
            total_minutes = int(td.total_seconds() // 60)
            horas, minutos = divmod(total_minutes, 60)
            return f"{horas}.{minutos:02d}"

        servicios_df["Horas Netas Reclamo"] = servicios_df["Horas Netas Reclamo"].apply(_fmt_horas)

    # Normaliza nombres de columna
    if "Servicio" not in reclamos_df.columns:

        reclamos_df.rename(columns={reclamos_df.columns[0]: "Servicio"}, inplace=True)
    if "Servicio" not in servicios_df:
        servicios_df.rename(columns={servicios_df.columns[0]: "Servicio"}, inplace=True)

    # Fecha para título
    try:
        fecha = pd.to_datetime(reclamos_df.iloc[0].get("Fecha"))
        if pd.isna(fecha):
            raise ValueError
    except Exception:
        fecha = pd.Timestamp.today()

    # Locale español (ignorar errores si no está instalado)
    for loc in ("es_ES.UTF-8", "es_ES", "es_AR.UTF-8", "es_AR"):
        try:
            locale.setlocale(locale.LC_TIME, loc)
            break
        except locale.Error:
            continue

    mes, anio = fecha.strftime("%B").upper(), fecha.strftime("%Y")

    # Conteo de reclamos
    resumen = reclamos_df.groupby("Servicio").size().reset_index(name="Reclamos")
    # Ordenar servicios de menor a mayor SLA y unir con reclamos
    if "SLA Entregado" in servicios_df.columns:
        servicios_df = servicios_df.sort_values("SLA Entregado")

    df = servicios_df.merge(resumen, on="Servicio", how="left")
    df["Reclamos"] = df["Reclamos"].fillna(0).astype(int)

    # Documento base
    if not (RUTA_PLANTILLA and os.path.exists(RUTA_PLANTILLA)):
        raise ValueError(f"Plantilla de SLA no encontrada: {RUTA_PLANTILLA}")
    doc = Document(RUTA_PLANTILLA)

    try:
        doc.add_heading(f"Informe SLA {mes} {anio}", level=0)
    except KeyError:
        doc.add_heading(f"Informe SLA {mes} {anio}", level=1)

    # Tabla principal
    headers = ["Servicio", *extra_cols, "Reclamos"]
    tbl = doc.add_table(rows=1, cols=len(headers), style="Table Grid")
    for i, h in enumerate(headers):
        tbl.rows[0].cells[i].text = h

    for _, fila in df.iterrows():
        row = tbl.add_row().cells
        for i, h in enumerate(headers):
            row[i].text = str(fila.get(h, ""))

    # Secciones texto
    etiquetas = {
        "Eventos sucedidos de mayor impacto en SLA:": eventos,
        "Conclusión:": conclusion,
        "Propuesta de mejora:": propuesta,
    }
    existentes = {p.text.split(":")[0] + ":" for p in doc.paragraphs}
    for etq, cont in etiquetas.items():
        if etq in existentes:
            for p in doc.paragraphs:
                if p.text.startswith(etq):
                    p.text = f"{etq} {cont}"
                    break
        elif cont:
            doc.add_paragraph(f"{etq} {cont}")

    # Guardar DOCX
    fd, ruta_docx = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    doc.save(ruta_docx)

    # Exportar PDF
    if exportar_pdf:
        ruta_pdf = os.path.splitext(ruta_docx)[0] + ".pdf"
        convertido = False

        if win32 and os.name == "nt":
            try:
                word = win32.Dispatch("Word.Application")
                word_doc = word.Documents.Open(ruta_docx)
                word_doc.SaveAs(ruta_pdf, FileFormat=17)
                word_doc.Close()
                word.Quit()
                convertido = True
            except Exception:
                logger.warning("Exportar PDF con win32 falló")

        if not convertido:
            try:
                from docx2pdf import convert  # type: ignore
                convert(ruta_docx, ruta_pdf)
                convertido = True

            except Exception:  # pragma: no cover
                logger.warning("No fue posible convertir a PDF con docx2pdf")


        if convertido:
            os.remove(ruta_docx)
            return ruta_pdf

    return ruta_docx
