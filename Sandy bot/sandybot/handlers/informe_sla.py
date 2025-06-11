"""Handler para generar informes de SLA."""

from __future__ import annotations

import logging
import os
import tempfile
import locale
from typing import Optional

import pandas as pd
from docx import Document
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from types import SimpleNamespace  # Fallback para stubs de test

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


# ────────────────────────── FLUJO DE INICIO ──────────────────────────
async def iniciar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pone al usuario en modo *informe_sla* y pide los dos archivos Excel."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_informe_sla")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "informe_sla")
    context.user_data.clear()
    context.user_data["archivos"] = [None, None]  # posiciones: [reclamos, servicios]

    # Botón para permitir cambiar la plantilla
    try:
        boton = InlineKeyboardButton("Actualizar plantilla", callback_data="sla_cambiar_plantilla")
        teclado = InlineKeyboardMarkup([[boton]])
    except Exception:  # Para stubs sin clases reales
        boton = SimpleNamespace(text="Actualizar plantilla", callback_data="sla_cambiar_plantilla")
        teclado = SimpleNamespace(inline_keyboard=[[boton]])

    await responder_registrando(
        mensaje,
        user_id,
        "informe_sla",
        "Enviá el Excel de **reclamos** y luego el de **servicios** para generar el informe.",
        "informe_sla",
        reply_markup=teclado,
    )


# ────────────────────────── FLUJO DE PROCESO ─────────────────────────
async def procesar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe dos Excel → botón “Procesar informe” → genera Word (y opcional PDF)."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en procesar_informe_sla")
        return

    user_id = update.effective_user.id
    archivos = context.user_data.setdefault("archivos", [None, None])

    # ─── Callback para cambiar plantilla ─────────────────────────────
    if update.callback_query and update.callback_query.data == "sla_cambiar_plantilla":
        context.user_data["cambiar_plantilla"] = True
        await update.callback_query.message.reply_text("Adjuntá la nueva plantilla .docx.")
        return

    # Guardar nueva plantilla
    if context.user_data.get("cambiar_plantilla"):
        if getattr(mensaje, "document", None):
            await _actualizar_plantilla_sla(update, context)
        else:
            await responder_registrando(
                mensaje,
                user_id,
                getattr(mensaje, "text", ""),
                "Adjuntá el archivo .docx para actualizar la plantilla.",
                "informe_sla",
            )
        return

    # ─── Callback «Procesar informe» ────────────────────────────────
    if update.callback_query and update.callback_query.data == "sla_procesar":
        reclamos_xlsx, servicios_xlsx = archivos
        try:
            ruta_final = _generar_documento_sla(reclamos_xlsx, servicios_xlsx)
            with open(ruta_final, "rb") as f:
                await update.callback_query.message.reply_document(f, filename=os.path.basename(ruta_final))
            os.remove(ruta_final)
            registrar_conversacion(
                user_id, "informe_sla", f"Documento {os.path.basename(ruta_final)} enviado", "informe_sla"
            )
        except Exception as e:  # pragma: no cover
            logger.error("Error generando informe SLA: %s", e)
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

    # ─── Recepción de archivos Excel ────────────────────────────────
    docs = [d for d in (getattr(mensaje, "document", None), *getattr(mensaje, "documents", [])) if d]
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
                mensaje, user_id, docs[-1].file_name,
                f"Archivo guardado. Falta el Excel de {falta}.", "informe_sla",
            )
            return

        # Ambos archivos listos → botón Procesar
        try:
            boton = InlineKeyboardButton("Procesar informe 🚀", callback_data="sla_procesar")
            keyboard = InlineKeyboardMarkup([[boton]])
        except Exception:  # fallback para stubs
            boton = SimpleNamespace(text="Procesar informe 🚀", callback_data="sla_procesar")
            keyboard = SimpleNamespace(inline_keyboard=[[boton]])

        await responder_registrando(
            mensaje, user_id, docs[-1].file_name,
            "Archivos cargados. Presioná *Procesar informe*.", "informe_sla",
            reply_markup=keyboard,
        )
        return

    # Ningún adjunto ni callback reconocido
    await responder_registrando(
        mensaje, user_id, getattr(mensaje, "text", ""),
        "Adjuntá los archivos de reclamos y servicios para comenzar.", "informe_sla",
    )


# ──────────────────── ACTUALIZAR PLANTILLA SLA ───────────────────────
async def _actualizar_plantilla_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda la plantilla enviada reemplazando la configuración actual."""
    mensaje = obtener_mensaje(update)
    user_id = update.effective_user.id
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
    except Exception as e:  # pragma: no cover
        logger.error("Error guardando plantilla SLA: %s", e)
        texto = "No se pudo guardar la plantilla."

    await responder_registrando(mensaje, user_id, archivo.file_name, texto, "informe_sla")


# ─────────────────── FUNCIÓN GENERADORA DE WORD ──────────────────────
def _generar_documento_sla(
    reclamos_xlsx: str,
    servicios_xlsx: str,
    eventos: Optional[str] = "",
    conclusion: Optional[str] = "",
    propuesta: Optional[str] = "",
    *,
    exportar_pdf: bool = False,
) -> str:
    """Combina datos y genera el documento SLA; opcionalmente exporta a PDF."""
    reclamos_df = pd.read_excel(reclamos_xlsx)
    servicios_df = pd.read_excel(servicios_xlsx)

    # Verificar columnas requeridas en el Excel de servicios
    columnas_requeridas = {"SLA Entregado", "Dirección", "Horas Netas Reclamo"}
    faltantes = columnas_requeridas - set(servicios_df.columns)
    if faltantes:
        logger.warning(
            "Faltan columnas en Excel de servicios: %s",
            ", ".join(sorted(faltantes)),
        )

    # Columnas opcionales a incluir si existen
    columnas_extra = [col for col in columnas_requeridas if col in servicios_df]

    # Normaliza nombres de columna
    if "Servicio" not in reclamos_df.columns:
        reclamos_df.rename(columns={reclamos_df.columns[0]: "Servicio"}, inplace=True)
    if "Servicio" not in servicios_df.columns:
        servicios_df.rename(columns={servicios_df.columns[0]: "Servicio"}, inplace=True)

    # Fecha para título
    try:
        fecha = pd.to_datetime(reclamos_df.iloc[0].get("Fecha"))
        if pd.isna(fecha):
            raise ValueError
    except Exception:
        fecha = pd.Timestamp.today()

    # Intentar locale español
    for loc in ("es_ES.UTF-8", "es_ES", "es_AR.UTF-8", "es_AR"):
        try:
            locale.setlocale(locale.LC_TIME, loc)
            break
        except locale.Error:
            continue

    mes = fecha.strftime("%B").upper()
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

    try:
        doc.add_heading(f"Informe SLA {mes} {anio}", level=0)
    except KeyError:  # Plantillas sin estilo 'Title'
        doc.add_heading(f"Informe SLA {mes} {anio}", level=1)

    # Tabla de resumen
    headers = ["Servicio", *columnas_extra, "Reclamos"]
    tabla = doc.add_table(rows=1, cols=len(headers), style="Table Grid")
    for i, col in enumerate(headers):
        tabla.rows[0].cells[i].text = col

    for _, fila in df.iterrows():
        celdas = tabla.add_row().cells
        for i, col in enumerate(headers):
            celdas[i].text = str(fila.get(col, ""))

    # Insertar textos personalizados
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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        ruta_docx = tmp.name
    doc.save(ruta_docx)

    # Exportar a PDF (Windows + win32) o intentar con docx2pdf
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
            except Exception as e:  # pragma: no cover
                logger.error("Error exportando PDF con win32: %s", e)

        if not convertido:
            try:
                from docx2pdf import convert  # type: ignore

                convert(ruta_docx, ruta_pdf)
                converted = True
            except Exception:  # pragma: no cover
                logger.warning("No fue posible convertir a PDF con docx2pdf")

        if converted:
            os.remove(ruta_docx)
            return ruta_pdf

    return ruta_docx
