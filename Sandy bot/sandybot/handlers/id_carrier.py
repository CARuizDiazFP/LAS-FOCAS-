"""Handler para completar IDs de servicio o Carrier desde un Excel."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
import pandas as pd
import os
import tempfile

from ..utils import obtener_mensaje
from ..database import SessionLocal, Servicio, Carrier, registrar_servicio
from .estado import UserState
from ..registrador import responder_registrando, registrar_conversacion

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
    await responder_registrando(
        mensaje,
        user_id,
        "id_carrier",
        "Enviá el Excel con las columnas 'ID Servicio' e 'ID Carrier' y lo completaré.",
        "id_carrier",
    )

async def procesar_identificador_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Completa los IDs faltantes en el Excel proporcionado."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.document:
        logger.warning("No se recibió documento en procesar_identificador_carrier.")
        return

    documento = mensaje.document
    if not documento.file_name.endswith(".xlsx"):
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            documento.file_name,
            "Solo acepto archivos Excel (.xlsx).",
            "id_carrier",
        )
        return

    file = await documento.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        await file.download_to_drive(tmp.name)

    try:
        df = pd.read_excel(tmp.name)
    except Exception as e:
        logger.error("Error leyendo Excel: %s", e)
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            documento.file_name,
            "No pude leer el Excel. Verificá el formato.",
            "id_carrier",
        )
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
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            documento.file_name,
            "El Excel debe tener las columnas 'ID Servicio' e 'ID Carrier'.",
            "id_carrier",
        )
        os.remove(tmp.name)
        return

    session = SessionLocal()
    try:
        for idx, row in df.iterrows():
            id_servicio = row.get(col_servicio)
            nombre_carrier = row.get(col_carrier)

            if pd.isna(id_servicio) and pd.isna(nombre_carrier):
                continue

            carrier_obj = None
            if pd.notna(nombre_carrier):
                nombre_carrier = str(nombre_carrier)
                carrier_obj = (
                    session.query(Carrier)
                    .filter(Carrier.nombre == nombre_carrier)
                    .first()
                )
                if not carrier_obj:
                    carrier_obj = Carrier(nombre=nombre_carrier)
                    session.add(carrier_obj)
                    session.commit()
                    session.refresh(carrier_obj)

            if pd.notna(id_servicio):
                try:
                    sid = int(id_servicio)
                except ValueError:
                    continue
                registrar_servicio(sid, carrier_id=carrier_obj.id if carrier_obj else None)
                if carrier_obj:
                    svc = session.get(Servicio, sid)
                    svc.carrier = nombre_carrier
                    session.commit()

    salida = os.path.join(
        tempfile.gettempdir(), f"identificador_carrier_{mensaje.from_user.id}.xlsx"
    )
    df.to_excel(salida, index=False)

    with open(salida, "rb") as f:
        await mensaje.reply_document(f, filename=os.path.basename(salida))
    registrar_conversacion(
        mensaje.from_user.id,
        documento.file_name,
        f"Documento {os.path.basename(salida)} enviado",
        "id_carrier",
    )
    session.close()

    os.remove(tmp.name)
    os.remove(salida)

    UserState.set_mode(mensaje.from_user.id, "")
    context.user_data.clear()
