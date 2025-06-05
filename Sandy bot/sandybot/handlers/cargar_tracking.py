"""Handler para la carga de trackings en la base de datos."""
from telegram import Update
from telegram.ext import ContextTypes
import logging
from ..utils import obtener_mensaje
from ..tracking_parser import TrackingParser
from ..config import config
from ..database import actualizar_tracking
from .estado import UserState

logger = logging.getLogger(__name__)
parser = TrackingParser()

async def iniciar_carga_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia el proceso solicitando el id del servicio."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_carga_tracking.")
        return
    user_id = mensaje.from_user.id
    UserState.set_mode(user_id, "cargar_tracking")
    context.user_data.clear()
    await mensaje.reply_text(
        "Ingresá el ID del servicio al que pertenece este tracking."
    )

async def guardar_tracking_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda el tracking en la base de datos."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.document:
        return

    user_id = mensaje.from_user.id
    servicio = context.user_data.get("id_servicio")
    if servicio is None:
        await mensaje.reply_text("Primero indicá el ID del servicio.")
        return

    documento = mensaje.document
    if not documento.file_name.endswith(".txt"):
        await mensaje.reply_text("Solo acepto archivos .txt para el tracking.")
        return

    archivo = await documento.get_file()
    ruta_destino = config.DATA_DIR / f"tracking_{servicio}.txt"
    await archivo.download_to_drive(str(ruta_destino))

    try:
        parser.clear_data()
        parser.parse_file(str(ruta_destino))
        camaras = parser._data[0][1]["camara"].astype(str).tolist()
        actualizar_tracking(servicio, str(ruta_destino), camaras)
        await mensaje.reply_text("✅ Tracking cargado y guardado correctamente.")
    except Exception as e:
        logger.error("Error al guardar tracking: %s", e)
        await mensaje.reply_text(f"Error al procesar el tracking: {e}")
    finally:
        UserState.set_mode(user_id, "")
        context.user_data.clear()
        parser.clear_data()
