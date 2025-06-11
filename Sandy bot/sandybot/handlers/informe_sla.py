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
    """Carga 2 Excel → botón Procesar → genera Word con informe SLA."""
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
                docs[-1].file_name_
