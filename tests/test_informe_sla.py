# + Nombre de archivo: test_informe_sla.py
# + Ubicación de archivo: tests/test_informe_sla.py
# User-provided custom instructions
"""Handler para generar informes de SLA."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

ROOT_DIR = Path(__file__).resolve().parents[1]
pkg = "sandybot.handlers"
if pkg not in sys.modules:
    handlers_pkg = ModuleType(pkg)
    handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
    sys.modules[pkg] = handlers_pkg
sys.path.append(str(ROOT_DIR / "Sandy bot"))
__package__ = pkg

import tests.telegram_stub  # Registra stubs de telegram

import logging
import os
import tempfile
import locale
from types import SimpleNamespace
from typing import Optional

os.environ.update(
    {
        "TELEGRAM_TOKEN": "x",
        "OPENAI_API_KEY": "x",
        "NOTION_TOKEN": "x",
        "NOTION_DATABASE_ID": "x",
        "DB_USER": "u",
        "DB_PASSWORD": "p",
        "SLACK_WEBHOOK_URL": "x",
        "SUPERVISOR_DB_ID": "x",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "sandy",
    }
)
os.environ["SLA_TEMPLATE_PATH"] = str(Path(tempfile.gettempdir()) / "sla.docx")

registrador_stub = ModuleType("sandybot.registrador")
async def _noop(*a, **k):
    pass
registrador_stub.responder_registrando = _noop
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules.setdefault("sandybot.registrador", registrador_stub)

import pandas as pd
from docx import Document
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from telegram.ext import ContextTypes

# ► Exportar a PDF (solo funciona en entornos donde esté disponible)
try:  # pragma: no cover
    import win32com.client as win32  # type: ignore
except Exception:  # pragma: no cover
    win32 = None

from sandybot.config import config
from ..utils import obtener_mensaje
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion

# Plantilla predeterminada
RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH

logger = logging.getLogger(__name__)


# ─────────────────────────────── INICIO ──────────────────────────────
async def iniciar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Coloca al usuario en modo *informe_sla* y solicita los dos Excel."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_informe_sla")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "informe_sla")
    context.user_data.clear()
    context.user_data["archivos"] = [None, None]  # [reclamos, servicios]

    # Botón para actualizar plantilla
    try:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Actualizar plantilla", callback_data="sla_cambiar_plantilla")]]
        )
    except Exception:  # fallback en tests
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


# ────────────────────────── PROCESO COMPLETO ─────────────────────────
async def procesar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestiona la carga de Excel, generación y envío del informe SLA."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en procesar_informe_sla")
        return

    user_id = update.effective_user.id
    archivos = context.user_data.setdefault("archivos", [None, None])

    # 1) ── Callback para cambiar plantilla ───────────────────────────
    if update.callback_query and update.callback_query.data == "sla_cambiar_plantilla":
        context.user_data["cambiar_plantilla"] = True
        await update.callback_query.message.reply_text("Adjuntá la nueva plantilla .docx.")
        return

    # 2) ── Guardar la nueva plantilla, si se solicitó ────────────────
    if context.user_data.get("cambiar_plantilla"):
        if getattr(mensaje, "document", None):
            await _actualizar_plantilla_sla(mensaje, context)
        else:
            await responder_registrando(
                mensaje,
                user_id,
                getattr(mensaje, "text", ""),
                "Adjuntá el archivo .docx para actualizar la plantilla.",
                "informe_sla",
            )
        return

    # 3) ── Callback «Procesar informe» ───────────────────────────────
    if update.callback_query and update.callback_query.data == "sla_procesar":
        try:
            ruta_final = _generar_documento_sla(*archivos)
            with open(ruta_final, "rb") as f:
                await update.callback_query.message.reply_document(f, filename=os.path.basename(ruta_final))
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
            if "ruta_final" in locals() and os.path.exists(ruta_final):
                os.remove(ruta_final)
            context.user_data.clear()
            UserState.set_mode(user_id, "")
        return

    # 4) ── Recepción de archivos Excel ───────────────────────────────
    docs = [d for d in (getattr(mensaje, "document", None), *getattr(mensaje, "documents", [])) if d]
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

        # Mostrar botón Procesar
        try:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Procesar informe 🚀", callback_data="sla_procesar")]]
            )
        except Exception:  # fallback stubs
            btn = SimpleNamespace(text="Procesar informe 🚀", callback_data="sla_procesar")
            kb = SimpleNamespace(inline_keyboard=[[btn]])

        await responder_registrando(
            mensaje, user_id, docs[-1].file_name,
            "Archivos cargados. Presioná *Procesar informe*.", "informe_sla", reply_markup=kb,
        )
        return

    # 5) ── Ningún adjunto ni callback reconocido ─────────────────────
    await responder_registrando(
        mensaje, user_id, getattr(mensaje, "text", ""),
        "Adjuntá los archivos de reclamos y servicios para comenzar.", "informe_sla",
    )


# ──────────────────── ACTUALIZAR PLANTILLA SLA ───────────────────────
async def _actualizar_plantilla_sla(mensaje, context):
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
    """Genera el documento SLA; si `exportar_pdf` es True intenta generar PDF."""
    reclamos_df = pd.read_excel(reclamos_xlsx)
    servicios_df = pd.read_excel(servicios_xlsx)

    columnas_extra = [c for c in ("SLA Entregado", "Dirección", "Horas Netas Reclamo") if c in servicios_df]

    # Normaliza nombres
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

    # Locale español (ignora errores si no está instalado)
    for loc in ("es_ES.UTF-8", "es_ES", "es_AR.UTF-8", "es_AR"):
        try:
            locale.setlocale(locale.LC_TIME, loc)
            break
        except locale.Error:
            continue

    mes, anio = fecha.strftime("%B").upper(), fecha.strftime("%Y")

    # Conteo de reclamos
    resumen = reclamos_df.groupby("Servicio").size().reset_index(name="Reclamos")
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

    # Tabla resumen
    headers = ["Servicio", *columnas_extra, "Reclamos"]
    tbl = doc.add_table(rows=1, cols=len(headers), style="Table Grid")
    for i, h in enumerate(headers):
        tbl.rows[0].cells[i].text = h

    for _, fila in df.iteritems():
        cells = tbl.add_row().cells
        for i, h in enumerate(headers):
            cells[i].text = str(fila.get(h, ""))

    # Etiquetas dinámicas
    etiquetas = {
        "Eventos sucedidos de mayor impacto en SLA:": eventos,
        "Conclusión:": conclusion,
        "Propuesta de mejora:": propuesta,
    }
    encontrados = set()
    for p in doc.paragraphs:
        for etq, cont in etiquetas.items():
            if p.text.strip().startswith(etq):
                p.text = f"{etq} {cont}"
                encontrados.add(etq)
                break
    for etq, cont in etiquetas.items():
        if etq not in encontrados and cont:
            doc.add_paragraph(f"{etq} {cont}")

    # Guardar DOCX
    fd, ruta_docx = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    doc.save(ruta_docx)

    # Exportar PDF (opcional)
    if exportar_pdf:
        pdf_path = os.path.splitext(ruta_docx)[0] + ".pdf"
        convertido = False

        if win32 and os.name == "nt":
            try:
                word = win32.Dispatch("Word.Application")
                word_doc = word.Documents.Open(ruta_docx)
                word_doc.SaveAs(pdf_path, FileFormat=17)
                word_doc.Close()
                word.Quit()
                convertido = True
            except Exception:
                logger.warning("Fallo exportando PDF con win32")

        if not convertido:
            try:
                from docx2pdf import convert  # type: ignore
                convert(ruta_docx, pdf_path)
                convertido = True
            except Exception:
                logger.warning("Fallo exportando PDF con docx2pdf")

        if convertido:
            os.remove(ruta_docx)
            return pdf_path

    return ruta_docx


# ─────────────────────────────── TESTS ────────────────────────────────

import asyncio
import pytest
from pathlib import Path
from tests.telegram_stub import Message, Document, Update, CallbackQuery


captura = {}


async def _fake_responder(mensaje, user_id, txt_usr, txt_resp, modo, **k):
    captura["texto"] = txt_resp
    captura["markup"] = k.get("reply_markup")


def _patch_registrador():
    globals()["responder_registrando"] = _fake_responder
    globals()["registrar_conversacion"] = lambda *a, **k: None


def test_procesar_archivos_en_orden(tmp_path):
    _patch_registrador()
    config.SLA_PLANTILLA_PATH = str(tmp_path / "tpl.docx")
    global RUTA_PLANTILLA
    RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH
    Path(RUTA_PLANTILLA).write_text("tpl")
    ctx = SimpleNamespace(user_data={})

    msg = Message()
    asyncio.run(iniciar_informe_sla(Update(message=msg), ctx))
    assert ctx.user_data["archivos"] == [None, None]

    doc1 = Document(file_name="recl.xlsx", content="a")
    asyncio.run(procesar_informe_sla(Update(message=Message(document=doc1)), ctx))
    assert "Falta el Excel de servicios" in captura["texto"]
    assert ctx.user_data["archivos"][0] and ctx.user_data["archivos"][1] is None

    doc2 = Document(file_name="serv.xlsx", content="b")
    asyncio.run(procesar_informe_sla(Update(message=Message(document=doc2)), ctx))
    assert "Procesar informe" in captura["texto"]


def test_actualizar_plantilla(tmp_path):
    _patch_registrador()
    ruta = tmp_path / "plantilla.docx"
    config.SLA_PLANTILLA_PATH = str(ruta)
    global RUTA_PLANTILLA
    RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH
    ctx = SimpleNamespace(user_data={})

    cb = CallbackQuery(message=Message())
    cb.data = "sla_cambiar_plantilla"
    asyncio.run(procesar_informe_sla(Update(callback_query=cb), ctx))
    assert ctx.user_data["cambiar_plantilla"] is True

    doc = Document(file_name="nueva.docx", content="x")
    asyncio.run(procesar_informe_sla(Update(message=Message(document=doc)), ctx))
    assert ruta.exists()
    assert "actualizada" in captura["texto"]
    assert "cambiar_plantilla" not in ctx.user_data


def test_finaliza_limpiando_user_data(tmp_path):
    _patch_registrador()
    config.SLA_PLANTILLA_PATH = str(tmp_path / "tpl.docx")
    global RUTA_PLANTILLA
    RUTA_PLANTILLA = config.SLA_PLANTILLA_PATH
    Path(RUTA_PLANTILLA).write_text("tpl")
    ctx = SimpleNamespace(user_data={"archivos": []})
    r = tmp_path / "re.xlsx"
    s = tmp_path / "se.xlsx"
    r.write_text("r")
    s.write_text("s")
    ctx.user_data["archivos"] = [str(r), str(s)]

    def _gen(_, __):
        final = tmp_path / "final.docx"
        final.write_text("x")
        return str(final)

    globals()["_generar_documento_sla"] = _gen
    cb = CallbackQuery(message=Message())
    cb.data = "sla_procesar"
    asyncio.run(procesar_informe_sla(Update(callback_query=cb), ctx))
    assert ctx.user_data == {}

