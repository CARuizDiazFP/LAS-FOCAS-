"""
Handler para la verificación de ingresos.
"""
from telegram import Update
from telegram.ext import ContextTypes
import logging
import os
import tempfile
import json
from sandybot.utils import obtener_mensaje
from ..database import obtener_servicio, actualizar_tracking
from ..config import config
import shutil
from .estado import UserState

logger = logging.getLogger(__name__)

async def manejar_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja la verificación de ingresos.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en manejar_ingresos.")
            return

        # Lógica para la verificación de ingresos
        await mensaje.reply_text("Verificación de ingresos en desarrollo.")
    except Exception as e:
        await mensaje.reply_text(f"Error al verificar ingresos: {e}")

async def iniciar_verificacion_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Inicia el proceso de verificación de ingresos.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en iniciar_verificacion_ingresos.")
            return

        user_id = mensaje.from_user.id
        UserState.set_mode(user_id, "ingresos")
        context.user_data.clear()

        await mensaje.reply_text(
            "Iniciando verificación de ingresos. "
            "Enviá primero el ID del servicio y luego adjuntá el archivo .txt."
        )
    except Exception as e:
        await mensaje.reply_text(f"Error al iniciar la verificación de ingresos: {e}")

async def procesar_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Procesa los ingresos enviados por el usuario.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje or not mensaje.document:
            logger.warning("No se recibió un documento en procesar_ingresos.")
            return

        user_id = mensaje.from_user.id
        id_servicio = context.user_data.get("id_servicio")
        if not id_servicio:
            await mensaje.reply_text("Primero indicá el ID del servicio en un mensaje de texto.")
            return

        documento = mensaje.document
        if not documento.file_name.endswith(".txt"):
            await mensaje.reply_text("Solo acepto archivos .txt para verificar ingresos.")
            return

        archivo = await documento.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            await archivo.download_to_drive(tmp.name)

        destino = config.DATA_DIR / f"ingresos_{id_servicio}_{documento.file_name}"
        shutil.move(tmp.name, destino)

        with open(destino, "r", encoding="utf-8") as f:
            camaras_archivo = [line.strip() for line in f if line.strip()]

        servicio = obtener_servicio(int(id_servicio))
        if not servicio:
            await mensaje.reply_text(f"No se encontró el servicio {id_servicio}.")
            return

        try:
            camaras_servicio = json.loads(servicio.camaras) if servicio.camaras else []
        except json.JSONDecodeError:
            camaras_servicio = []

        set_archivo = set(camaras_archivo)
        set_servicio = set(camaras_servicio)

        coinciden = sorted(set_archivo & set_servicio)
        faltantes = sorted(set_servicio - set_archivo)
        adicionales = sorted(set_archivo - set_servicio)

        respuesta = ["📋 Resultado de la verificación:"]
        if coinciden:
            respuesta.append("✅ Coinciden: " + ", ".join(coinciden))
        if faltantes:
            respuesta.append("❌ Faltan en archivo: " + ", ".join(faltantes))
        if adicionales:
            respuesta.append("⚠️ No esperadas: " + ", ".join(adicionales))
        if len(respuesta) == 1:
            respuesta.append("No se detectaron cámaras para comparar.")

        await mensaje.reply_text("\n".join(respuesta))

        actualizar_tracking(int(id_servicio), trackings_txt=[str(destino)])

        UserState.set_mode(user_id, "")
        context.user_data.pop("id_servicio", None)
    except Exception as e:
        await mensaje.reply_text(f"Error al procesar ingresos: {e}")

