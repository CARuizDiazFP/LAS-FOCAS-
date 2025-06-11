# + Nombre de archivo: informe_sla.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/informe_sla.py
# User-provided custom instructions
"""Handler para generar informes de SLA."""

from __future__ import annotations

import logging
import os
import tempfile

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
    # Se reservan dos posiciones: 0 para reclamos y 1 para servicios
    context.user_data["archivos"] = [None, None]

    await responder_registrando(
        mensaje,
        user_id,
        "informe_sla",
        "Enviá el Excel de **reclamos** y luego el de **servicios** para generar el informe.",
        "informe_sla",
    )


# ────────────────────────── FLUJO DE PROCESO ─────────────────────────
async def procesar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestiona la generación del informe SLA paso a paso."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en procesar_informe_sla")
        return

    user_id = update.effective_user.id

    # ───── Callback «Procesar informe» ─────
    if update.callback_query and update.callback_query.data == "sla_procesar":
        rec, serv = context.user_data.get("archivos", [None, None])
        try:
            ruta_final = _generar_documento_sla(rec, serv, "", "", "")
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
            await responder_registrando(
                update.callback_query.message,
                user_id,
                os.path.basename(rec or ""),
                "💥 Algo falló generando el informe de SLA.",
                "informe_sla",
            )
        finally:
            for p in context.user_data.get("archivos", []):
                try:
                    os.remove(p)
                except OSError:
                    pass
            context.user_data.clear()
            UserState.set_mode(user_id, "")
        return

    # ───── Paso inicial: recepción de los 2 Excel ─────
    archivos = context.user_data.setdefault("archivos", [None, None])
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
                # Detección básica por nombre
                if "recl" in nombre and archivos[0] is None:
                    archivos[0] = tmp.name
                elif "serv" in nombre and archivos[1] is None:
                    archivos[1] = tmp.name
                elif archivos[0] is None:
                    archivos[0] = tmp.name
                else:
                    archivos[1] = tmp.name

        # Verificamos si faltan archivos
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

        # Ambos archivos listos → ofrecer botón procesar
        context.user_data["esperando_eventos"] = False
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Procesar informe 🚀", callback_data="sla_procesar")]]
        )
        await responder_registrando(
            mensaje,
            user_id,
            docs[-1].file_name,
            "Archivos cargados. Presioná *Procesar informe*.",
            "informe_sla",
            reply_markup=keyboard,
        )
        return

    # ───── Paso eventos ─────
    # if context.user_data.get("esperando_eventos"):
    #     context.user_data["eventos"] = getattr(mensaje, "text", "")
    #     context.user_data["esperando_eventos"] = False
    #     context.user_data["esperando_conclusion"] = True
    #     await responder_registrando(
    #         mensaje,
    #         user_id,
    #         mensaje.text,
    #         "Indicá la conclusión.",
    #         "informe_sla",
    #     )
    #     return

    # ───── Paso conclusión ─────
    # if context.user_data.get("esperando_conclusion"):
    #     context.user_data["conclusion"] = getattr(mensaje, "text", "")
    #     context.user_data["esperando_conclusion"] = False
    #     context.user_data["esperando_propuesta"] = True
    #     await responder_registrando(
    #         mensaje,
    #         user_id,
    #         mensaje.text,
    #         "¿Cuál es la propuesta de mejora?",
    #         "informe_sla",
    #     )
    #     return

    # ───── Paso propuesta y generación final ─────
    # if context.user_data.get("esperando_propuesta"):
    #     context.user_data["propuesta"] = getattr(mensaje, "text", "")
    #     context.user_data["esperando_propuesta"] = False
    #
    #     eventos = context.user_data.get("eventos")
    #     conclusion = context.user_data.get("conclusion")
    #     propuesta = context.user_data.get("propuesta")
    #     rec, serv = context.user_data.get("archivos", [None, None])
    #
    #     try:
    #         ruta_final = _generar_documento_sla(rec, serv, eventos, conclusion, propuesta)
    #         with open(ruta_final, "rb") as f:
    #             await mensaje.reply_document(f, filename=os.path.basename(ruta_final))
    #
    #         registrar_conversacion(
    #             user_id,
    #             "informe_sla",
    #             f"Documento {os.path.basename(ruta_final)} enviado",
    #             "informe_sla",
    #         )
    #     except Exception as e:  # pragma: no cover
    #         logger.error("Error generando informe SLA: %s", e)
    #         await responder_registrando(
    #             mensaje,
    #             user_id,
    #             os.path.basename(rec or ""),
    #             "💥 Algo falló generando el informe de SLA.",
    #             "informe_sla",
    #         )
    #     finally:
    #         # Limpieza de temporales y restablecimiento de estado
    #         for p in archivos:
    #             try:
    #                 os.remove(p)
    #             except OSError:
    #                 pass
    #         context.user_data.clear()
    #         UserState.set_mode(user_id, "")
    #     return

    # Estado no reconocido
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
    eventos: str | None = None,
    conclusion: str | None = None,
    propuesta: str | None = None,
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

    # Insertar textos personalizados
    etiquetas = {
        "Eventos sucedidos de mayor impacto en SLA:": eventos,
        "Conclusión:": conclusion,
        "Propuesta de mejora:": propuesta,
    }
    encontrados = set()
    for p in doc.paragraphs:
        texto = p.text.strip()
        for etiqueta, contenido in etiquetas.items():
            if texto.startswith(etiqueta):
                p.text = f"{etiqueta} {contenido or ''}"
                encontrados.add(etiqueta)
                break
    for etiqueta, contenido in etiquetas.items():
        if etiqueta not in encontrados and contenido:
            doc.add_paragraph(f"{etiqueta} {contenido}")

    # Guardado temporal
    nombre_arch = "InformeSLA.docx"
    ruta_salida = os.path.join(tempfile.gettempdir(), nombre_arch)
    doc.save(ruta_salida)
    return ruta_salida
