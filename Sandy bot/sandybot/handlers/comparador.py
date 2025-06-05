"""
Handler para la comparación de trazados de fibra óptica.
"""
from telegram import Update
from telegram.ext import ContextTypes
import logging
import os
import tempfile
from sandybot.tracking_parser import TrackingParser
from sandybot.utils import obtener_mensaje
from .estado import UserState

logger = logging.getLogger(__name__)
parser = TrackingParser()

async def iniciar_comparador(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Inicia el proceso de comparación de trazados de fibra óptica.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en iniciar_comparador.")
            return

        user_id = mensaje.from_user.id
        UserState.set_mode(user_id, "comparador")
        context.user_data["trackings"] = []
        await mensaje.reply_text(
            "Iniciando comparación de trazados de fibra óptica. "
            "Adjuntá los trackings (.txt) y luego enviá /procesar."
        )
    except Exception as e:
        await mensaje.reply_text(f"Error al iniciar la comparación: {e}")


async def recibir_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Recibe y procesa el archivo de tracking enviado por el usuario.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje or not mensaje.document:
            logger.warning("No se recibió un documento en recibir_tracking.")
            return

        documento = mensaje.document
        if not documento.file_name.endswith(".txt"):
            await mensaje.reply_text(
                "🙄 Solo acepto archivos .txt para comparar trazados."
            )
            return

        archivo = await documento.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            await archivo.download_to_drive(tmp.name)

        user_id = mensaje.from_user.id
        UserState.set_tracking(user_id, tmp.name)
        context.user_data.setdefault("trackings", []).append(tmp.name)
        await mensaje.reply_text(
            "📎 Archivo recibido. Podés adjuntar otro o enviar /procesar."
        )
    except Exception as e:
        await mensaje.reply_text(f"Error al recibir el archivo de tracking: {e}")

async def procesar_comparacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Procesa los datos enviados para realizar una comparación detallada.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en procesar_comparacion.")
            return

        user_id = mensaje.from_user.id
        trackings = context.user_data.get("trackings", [])
        if len(trackings) < 2:
            await mensaje.reply_text(
                "¿Procesar qué? Necesito al menos dos archivos de tracking."
            )
            UserState.set_mode(user_id, "")
            context.user_data["trackings"] = []
            return

        await mensaje.reply_text(
            "Procesando comparación, aguarde. Se generará un informe con cámaras comunes..."
        )

        try:
            parser.clear_data()
            for ruta in trackings:
                parser.parse_file(ruta)

            salida = os.path.join(
                tempfile.gettempdir(), f"ComparacionFO_{user_id}.xlsx"
            )
            parser.generate_excel(salida)

            with open(salida, "rb") as doc:
                await mensaje.reply_document(doc, filename=os.path.basename(salida))

        except Exception as e:
            logger.error("Error generando Excel: %s", e)
            await mensaje.reply_text(f"💥 Algo falló al generar el Excel: {e}")
        finally:
            for ruta in trackings:
                try:
                    os.remove(ruta)
                except OSError:
                    pass
            parser.clear_data()
            if 'salida' in locals():
                try:
                    os.remove(salida)
                except OSError:
                    pass
            context.user_data["trackings"] = []
            UserState.set_mode(user_id, "")
    except Exception as e:
        await mensaje.reply_text(f"Error al procesar la comparación: {e}")

