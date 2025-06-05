"""
Handler para la comparación de trazados de fibra óptica.
"""
from telegram import Update
from telegram.ext import ContextTypes
import logging
import os
import tempfile
from datetime import datetime
from sandybot.tracking_parser import TrackingParser
from sandybot.utils import obtener_mensaje
from sandybot.database import (
    actualizar_tracking,
    obtener_servicio,
    crear_servicio,
)
from sandybot.config import config
import shutil
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

        # Si esta función se llama desde un callback, ``mensaje.from_user`` será
        # el bot. Empleamos ``update.effective_user`` para asignar el modo al
        # usuario que inició la acción.
        user_id = update.effective_user.id
        UserState.set_mode(user_id, "comparador")
        context.user_data.clear()
        context.user_data["trackings"] = []
        context.user_data["servicios"] = []
        context.user_data["esperando_servicio"] = True
        await mensaje.reply_text(
            "Iniciando comparación de trazados de fibra óptica. "
            "Indicá el número de servicio a comparar."
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

        servicio = context.user_data.get("servicio_actual")
        if not servicio:
            await mensaje.reply_text("Indicá primero el número de servicio.")
            return

        archivo = await documento.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            await archivo.download_to_drive(tmp.name)

        ruta_destino = config.DATA_DIR / f"tracking_{servicio}.txt"
        rutas_extra = []
        if ruta_destino.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            historico = config.HISTORICO_DIR / f"tracking_{servicio}_{timestamp}.txt"
            ruta_destino.rename(historico)
            rutas_extra.append(str(historico))

        shutil.move(tmp.name, ruta_destino)
        try:
            parser.clear_data()
            parser.parse_file(str(ruta_destino))
            camaras = parser._data[0][1]["camara"].astype(str).tolist()
            rutas_extra.append(str(ruta_destino))
            if not obtener_servicio(servicio):
                crear_servicio(id=servicio)
            actualizar_tracking(servicio, str(ruta_destino), camaras, rutas_extra)
            context.user_data.setdefault("servicios", []).append(servicio)
            context.user_data.setdefault("trackings", []).append(
                (str(ruta_destino), documento.file_name)
            )
            await mensaje.reply_text(
                "📎 Tracking registrado. Indicá otro servicio o ejecutá /procesar."
            )
        except Exception as e:
            logger.error("Error procesando tracking: %s", e)
            await mensaje.reply_text(f"Error al procesar el tracking: {e}")
        finally:
            parser.clear_data()
            context.user_data.pop("esperando_archivo", None)
            context.user_data.pop("servicio_actual", None)
            context.user_data["esperando_servicio"] = True
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
                "¿Procesar qué? Necesito al menos dos servicios con tracking."
            )
            UserState.set_mode(user_id, "")
            context.user_data.clear()
            return

        await mensaje.reply_text(
            "Procesando comparación, aguarde. Se generará un informe con cámaras comunes..."
        )

        try:
            parser.clear_data()
            for ruta, nombre in trackings:
                parser.parse_file(ruta, sheet_name=nombre)

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
            parser.clear_data()
            if 'salida' in locals():
                try:
                    os.remove(salida)
                except OSError:
                    pass
            context.user_data.clear()
            UserState.set_mode(user_id, "")
    except Exception as e:
        await mensaje.reply_text(f"Error al procesar la comparación: {e}")

