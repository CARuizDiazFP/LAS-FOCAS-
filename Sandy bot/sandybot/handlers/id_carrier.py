"""Handler para completar IDs de servicio o Carrier desde un Excel."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import pandas as pd
import os
import tempfile

from ..utils import obtener_mensaje
from ..database import SessionLocal, Servicio
from .estado import UserState

logger = logging.getLogger(__name__)

async def iniciar_identificador_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Solicita el archivo Excel con IDs de servicio y carrier."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_identificador_carrier.")
        return

    user_id = update.effective_user.id
    UserState.set_mode(user_id, "id_carrier")
    context.user_data.clear()
    await mensaje.reply_text(
        "Enviá el Excel con las columnas 'ID Servicio' e 'ID Carrier' y lo completaré."
    )

async def procesar_identificador_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Completa los IDs faltantes en el Excel proporcionado."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.document:
        logger.warning("No se recibió documento en procesar_identificador_carrier.")
        return

    documento = mensaje.document
    if not documento.file_name.endswith(".xlsx"):
        await mensaje.reply_text("Solo acepto archivos Excel (.xlsx).")
        return

    file = await documento.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        await file.download_to_drive(tmp.name)

    try:
        df = pd.read_excel(tmp.name)
    except Exception as e:
        logger.error("Error leyendo Excel: %s", e)
        await mensaje.reply_text("No pude leer el Excel. Verificá el formato.")
        os.remove(tmp.name)
        return

    col_servicio = None
    col_carrier = None
    for col in df.columns:
        nombre = str(col).lower()
        if "servicio" in nombre:
            col_servicio = col
        if "carrier" in nombre:
            col_carrier = col

    if col_servicio is None or col_carrier is None:
        await mensaje.reply_text(
            "El Excel debe tener las columnas 'ID Servicio' e 'ID Carrier'."
        )
        os.remove(tmp.name)
        return

    session = SessionLocal()
    try:
        for idx, row in df.iterrows():
            id_servicio = row.get(col_servicio)
            id_carrier = row.get(col_carrier)

            if pd.isna(id_servicio) and pd.isna(id_carrier):
                continue

            if pd.isna(id_servicio) and pd.notna(id_carrier):
                servicio = (
                    session.query(Servicio)
                    .filter(Servicio.id_carrier == str(id_carrier))
                    .first()
                )
                if servicio:
                    df.at[idx, col_servicio] = servicio.id

            elif pd.isna(id_carrier) and pd.notna(id_servicio):
                servicio = session.get(Servicio, int(id_servicio))
                if servicio and servicio.id_carrier:
                    df.at[idx, col_carrier] = servicio.id_carrier
    finally:
        session.close()

    salida = os.path.join(
        tempfile.gettempdir(), f"identificador_carrier_{mensaje.from_user.id}.xlsx"
    )
    df.to_excel(salida, index=False)

    with open(salida, "rb") as f:
        await mensaje.reply_document(f, filename=os.path.basename(salida))

    os.remove(tmp.name)
    os.remove(salida)

    UserState.set_mode(mensaje.from_user.id, "")
    context.user_data.clear()
