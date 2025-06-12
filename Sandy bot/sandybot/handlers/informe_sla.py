# + Nombre de archivo: informe_sla.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/informe_sla.py
# User-provided custom instructions
"""Handler para generar informes de SLA."""

from __future__ import annotations

import logging
import os
import tempfile
import locale
import copy
from types import SimpleNamespace
from typing import Optional

import pandas as pd
from docx import Document
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Dependencia opcional para exportar PDF y modificar DOCX en Windows
try:  # pragma: no cover
    import win32com.client as win32  # type: ignore
    import pythoncom  # type: ignore
except Exception:  # pragma: no cover
    win32 = None
    pythoncom = None

from sandybot.config import config
from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion
from .. import database as bd

# Plantilla de Word definida en la configuración
RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH

logger = logging.getLogger(__name__)


def _guardar_reclamos(df: pd.DataFrame) -> None:
    """Registra en la base los reclamos del DataFrame."""
    if "Número Reclamo" not in df.columns:
        return

    col_servicio = None
    for c in ["Servicio", "Número Línea", "Número Primer Servicio"]:
        if c in df.columns:
            col_servicio = c
            break
    if not col_servicio:
        return

    for _, fila in df.iterrows():
        sid = fila.get(col_servicio)
        numero = fila.get("Número Reclamo")
        if pd.isna(sid) or pd.isna(numero):
            continue
        try:
            sid_int = int(str(sid).replace(".0", ""))
        except ValueError:
            continue
        fecha = None
        for c in ["Fecha Inicio Reclamo", "Fecha Inicio Problema Reclamo"]:
            if c in df.columns and not pd.isna(fila.get(c)):
                fecha = pd.to_datetime(fila[c], errors="coerce")
                break
        descripcion = fila.get("Tipo Solución Reclamo")
        bd.crear_reclamo(sid_int, str(numero), fecha_inicio=fecha, descripcion=descripcion)


def identificar_excel(path: str) -> str:
    """Clasifica el Excel como "reclamos" o "servicios"."""
    df = pd.read_excel(path, nrows=0)
    columnas = set(df.columns)

    if {"Número Reclamo", "Fecha Inicio Problema Reclamo"} & columnas:
        return "reclamos"
    if {"SLA Entregado", "Número Primer Servicio"} & columnas:
        return "servicios"

    raise ValueError(f"No se pudo identificar el tipo de Excel: {path}")


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

            try:
                tipo = identificar_excel(tmp.name)
            except Exception as exc:  # pragma: no cover
                logger.warning("No se pudo clasificar %s: %s", doc.file_name, exc)
                tipo = "reclamos" if archivos[0] is None else "servicios"

            if tipo == "reclamos":
                if archivos[0] is None:
                    archivos[0] = tmp.name
                else:
                    archivos[1] = tmp.name
            else:
                if archivos[1] is None:
                    archivos[1] = tmp.name
                else:
                    archivos[0] = tmp.name

            if None in archivos:
                n = 2 - archivos.count(None)
                await responder_registrando(
                    mensaje,
                    user_id,
                    doc.file_name,
                    f"Recibido archivo {n}/2 ({tipo})",
                    "informe_sla",
                )
                return

        # Si llegamos aquí, ambos archivos están presentes

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
    """Genera el documento SLA.

    El contenido se vuelca en la tabla predefinida de la plantilla y,
    si ``exportar_pdf`` es ``True`` se intenta guardar una versión en PDF.
    """
    reclamos_df = pd.read_excel(reclamos_xlsx)
    servicios_df = pd.read_excel(servicios_xlsx)
    _guardar_reclamos(reclamos_df)
    servicios_df.columns = (
        servicios_df.columns
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    def _to_timedelta(valor: object) -> pd.Timedelta:
        try:
            return pd.to_timedelta(valor)
        except Exception:
            try:
                return pd.to_timedelta(float(str(valor).replace(",", ".")), unit="h")
            except Exception:
                return pd.Timedelta(0)

    def _fmt_td(td: pd.Timedelta) -> str:
        total_seconds = int(td.total_seconds())
        horas = total_seconds // 3600
        minutos = (total_seconds % 3600) // 60
        segundos = total_seconds % 60
        return f"{horas:03d}:{minutos:02d}:{segundos:02d}"

    # Formatea "Horas Netas Reclamo" si tiene valores numéricos
    if "Horas Netas Reclamo" in servicios_df.columns:
        servicios_df["Horas Netas Reclamo"] = servicios_df["Horas Netas Reclamo"].apply(
            lambda v: _fmt_td(_to_timedelta(v)) if not pd.isna(v) else v
        )

    if "Horas Reclamos Todos" in servicios_df.columns:
        servicios_df["Horas Reclamos Todos"] = servicios_df["Horas Reclamos Todos"].apply(
            lambda v: _fmt_td(_to_timedelta(v))
        )

    # Normaliza nombres de columna
    if "Servicio" not in reclamos_df.columns:

        reclamos_df.rename(columns={reclamos_df.columns[0]: "Servicio"}, inplace=True)

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


    # Documento base
    if not (RUTA_PLANTILLA and os.path.exists(RUTA_PLANTILLA)):
        raise ValueError(f"Plantilla de SLA no encontrada: {RUTA_PLANTILLA}")
    doc = Document(RUTA_PLANTILLA)

    try:
        doc.add_heading(f"Informe SLA {mes} {anio}", level=0)
    except KeyError:
        doc.add_heading(f"Informe SLA {mes} {anio}", level=1)

    # Tabla principal existente en la plantilla
    if not doc.tables:
        raise ValueError("La plantilla debe incluir una tabla para el SLA")
    tabla = doc.tables[0]

    while len(tabla.rows) > 1:
        tabla._tbl.remove(tabla.rows[1]._tr)

    columnas = [
        "Tipo Servicio",
        "Número Línea",
        "Nombre Cliente",
        "Horas Reclamos Todos",
        "SLA",
    ]

    if "SLA" not in servicios_df.columns and "SLA Entregado" in servicios_df.columns:
        servicios_df = servicios_df.rename(columns={"SLA Entregado": "SLA"})

    if "SLA" in servicios_df.columns:
        servicios_df["SLA"] = servicios_df["SLA"].apply(
            lambda v: float(str(v).replace(",", ".")) if not pd.isna(v) else 0
        )

    faltantes = [c for c in columnas if c not in servicios_df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en servicios.xlsx: {', '.join(faltantes)}")

    df_tabla = servicios_df[columnas].sort_values("SLA", ascending=False)

    for _, fila in df_tabla.iterrows():
        nueva = copy.deepcopy(tabla.rows[0]._tr)
        tabla._tbl.append(nueva)
        celdas = tabla.rows[-1].cells
        celdas[0].text = str(fila["Tipo Servicio"])
        celdas[1].text = str(fila["Número Línea"])
        celdas[2].text = str(fila.get("Nombre Cliente", ""))
        celdas[3].text = str(fila.get("Horas Reclamos Todos", ""))
        celdas[4].text = f"{float(fila['SLA']) * 100:.2f}%"

    template2 = template3 = None
    if len(doc.tables) > 1:
        template2 = copy.deepcopy(doc.tables[1]._tbl)
    if len(doc.tables) > 2:
        template3 = copy.deepcopy(doc.tables[2]._tbl)

    for t in doc.tables[1:]:
        t._tbl.getparent().remove(t._tbl)

    cols_r = [
        "Número Línea",
        "Número Reclamo",
        "Horas Netas Reclamo",
        "Tipo Solución Reclamo",
        "Fecha Inicio Reclamo",
    ]

    etiquetas = {
        "Eventos sucedidos de mayor impacto en SLA:": eventos,
        "Conclusión:": conclusion,
        "Propuesta de mejora:": propuesta,
    }

    for _, fila in df_tabla.iterrows():
        if template2 is not None:
            doc._body._element.append(copy.deepcopy(template2))
            tabla2 = doc.tables[-1]
            filtros = []
            if "Número Línea" in reclamos_df.columns:
                filtros.append(reclamos_df["Número Línea"] == fila["Número Línea"])
            if "Número Primer Servicio" in reclamos_df.columns:
                filtros.append(reclamos_df["Número Primer Servicio"] == fila["Número Línea"])
            if filtros:
                filtro = filtros[0]
                for f in filtros[1:]:
                    filtro |= f
                recl_srv = reclamos_df[filtro]
            else:
                recl_srv = pd.DataFrame()
            if not recl_srv.empty:
                cliente = recl_srv.iloc[0].get(
                    "Cliente",
                    recl_srv.iloc[0].get("Nombre Cliente", fila.get("Nombre Cliente", "")),
                )
                ticket = recl_srv.iloc[0].get("N° de Ticket", recl_srv.iloc[0].get("Número Reclamo", ""))
                domicilio = recl_srv.iloc[0].get("Domicilio", fila.get("Domicilio", ""))
            else:
                cliente = fila.get("Nombre Cliente", "")
                ticket = ""
                domicilio = fila.get("Domicilio", "")

            info = {
                "Servicio": fila.get("Tipo Servicio", ""),
                "SLA": f"{float(fila['SLA']) * 100:.2f}%",
                "Cliente": cliente,
                "N° de Ticket": ticket,
                "Domicilio": domicilio,
            }
            for r in tabla2.rows:
                key = r.cells[0].text.strip()
                if key in info:
                    r.cells[1].text = str(info[key])

        if template3 is not None:
            doc._body._element.append(copy.deepcopy(template3))
            tabla3 = doc.tables[-1]
            while len(tabla3.rows) > 1:
                tabla3._tbl.remove(tabla3.rows[1]._tr)
            filtros = []
            if "Número Línea" in reclamos_df.columns:
                filtros.append(reclamos_df["Número Línea"] == fila["Número Línea"])
            if "Número Primer Servicio" in reclamos_df.columns:
                filtros.append(reclamos_df["Número Primer Servicio"] == fila["Número Línea"])
            if filtros:
                filtro = filtros[0]
                for f in filtros[1:]:
                    filtro |= f
                recl_srv = reclamos_df[filtro]
            else:
                recl_srv = pd.DataFrame()
            faltantes = [c for c in cols_r if c not in recl_srv.columns]
            total = pd.Timedelta(0)
            if not faltantes:
                for _, fr in recl_srv[cols_r].iterrows():
                    nueva = copy.deepcopy(tabla3.rows[0]._tr)
                    tabla3._tbl.append(nueva)
                    c = tabla3.rows[-1].cells
                    c[0].text = str(fr["Número Línea"])
                    c[1].text = str(fr["Número Reclamo"])
                    td = _to_timedelta(fr["Horas Netas Reclamo"])
                    total += td
                    c[2].text = _fmt_td(td)
                    c[3].text = str(fr["Tipo Solución Reclamo"])
                    c[4].text = str(fr["Fecha Inicio Reclamo"])
                nueva = copy.deepcopy(tabla3.rows[0]._tr)
                tabla3._tbl.append(nueva)
                c = tabla3.rows[-1].cells
                c[0].text = "Total"
                c[1].text = ""
                c[2].text = _fmt_td(total)
                c[3].text = ""
                c[4].text = ""
            elif faltantes:
                logger.warning("Faltan columnas en reclamos.xlsx: %s", ", ".join(faltantes))

        for etq, cont in etiquetas.items():
            if cont:
                doc.add_paragraph(f"{etq} {cont}")

    # Guardar DOCX
    fd, ruta_docx = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    doc.save(ruta_docx)

    if win32 is not None:
        modificar_sla_con_pythoncom(ruta_docx, mes, anio)
    else:
        logger.info(
            "Omitiendo modificación por COM; esta funcionalidad solo está disponible en Windows."
        )

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


def modificar_sla_con_pythoncom(path: str, mes: str, anio: str) -> None:
    """Ajusta el título del documento SLA mediante COM en Windows."""
    pythoncom.CoInitialize()
    try:
        word_app = win32.Dispatch("Word.Application")
        word_app.Visible = False
        doc = word_app.Documents.Open(path)
        titulo = f"Informe SLA {mes} {anio}"
        for shape in doc.Shapes:
            if shape.TextFrame.HasText and "Informe SLA" in shape.TextFrame.TextRange.Text:
                shape.TextFrame.TextRange.Text = titulo
        doc.SaveAs(path)
        doc.Close()
        word_app.Quit()
    except Exception as exc:
        logger.error("Error al modificar SLA con COM: %s", exc)
    finally:
        pythoncom.CoUninitialize()
