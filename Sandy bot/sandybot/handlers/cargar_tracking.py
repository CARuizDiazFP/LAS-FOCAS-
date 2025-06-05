"""Handler para la carga de trackings en la base de datos."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
import re
from pathlib import Path
from datetime import datetime
from ..utils import obtener_mensaje
from ..tracking_parser import TrackingParser
from ..config import config
from ..database import actualizar_tracking, obtener_servicio, crear_servicio
from .estado import UserState

logger = logging.getLogger(__name__)
parser = TrackingParser()

async def iniciar_carga_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia el proceso solicitando el archivo de tracking."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        logger.warning("No se recibió mensaje en iniciar_carga_tracking.")
        return

    # ``mensaje`` proviene del botón con el menú, por lo que su ``from_user``
    # es el propio bot. Utilizamos ``update.effective_user`` para obtener el
    # ID real del usuario que hizo clic y así mantener su estado correctamente.
    user_id = update.effective_user.id

    UserState.set_mode(user_id, "cargar_tracking")
    context.user_data.clear()
    await mensaje.reply_text("Enviá el archivo .txt del tracking para comenzar.")

async def guardar_tracking_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda el tracking en la base de datos."""
    mensaje = obtener_mensaje(update)
    if not mensaje and "tracking_temp" not in context.user_data:
        return

    user_id = mensaje.from_user.id if mensaje else update.effective_user.id
    documento = mensaje.document if mensaje else None

    # Si llegó un documento, guardarlo temporalmente
    if documento:
        if not documento.file_name.endswith(".txt"):
            await mensaje.reply_text("Solo acepto archivos .txt para el tracking.")
            return

        archivo = await documento.get_file()
        ruta_temp = config.DATA_DIR / f"tmp_{documento.file_unique_id}.txt"
        await archivo.download_to_drive(str(ruta_temp))
        context.user_data["tracking_temp"] = str(ruta_temp)

        if "id_servicio" not in context.user_data:
            match = re.search(r"_(\d+)", documento.file_name)
            if match:
                context.user_data["id_servicio_detected"] = int(match.group(1))
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Procesar tracking", callback_data="confirmar_tracking"
                            ),
                            InlineKeyboardButton(
                                "Modificar ID", callback_data="cambiar_id_tracking"
                            ),
                        ]
                    ]
                )
                await mensaje.reply_text(
                    f"Se detectó el ID {match.group(1)}. ¿Deseás asociarlo a este servicio?",
                    reply_markup=keyboard,
                )
            else:
                await mensaje.reply_text(
                    "No pude detectar el ID. Escribí el número del servicio."
                )
            context.user_data["confirmar_id"] = True
            return

    servicio = context.user_data.get("id_servicio")
    ruta_temp = context.user_data.get("tracking_temp")
    if servicio is None or ruta_temp is None:
        await mensaje.reply_text("Falta el ID o el archivo de tracking.")
        return

    ruta_destino = config.DATA_DIR / f"tracking_{servicio}.txt"
    rutas_extra = []
    if ruta_destino.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        historico = config.HISTORICO_DIR / f"tracking_{servicio}_{timestamp}.txt"
        ruta_destino.rename(historico)
        rutas_extra.append(str(historico))

    Path(ruta_temp).rename(ruta_destino)

    try:
        parser.clear_data()
        parser.parse_file(str(ruta_destino))
        camaras = parser._data[0][1]["camara"].astype(str).tolist()
        rutas_extra.append(str(ruta_destino))
        id_servicio = int(servicio)
        if not obtener_servicio(id_servicio):
            crear_servicio(id=id_servicio)
        actualizar_tracking(id_servicio, str(ruta_destino), camaras, rutas_extra)
        await mensaje.reply_text("✅ Tracking cargado y guardado correctamente.")
    except Exception as e:
        logger.error("Error al guardar tracking: %s", e)
        await mensaje.reply_text(f"Error al procesar el tracking: {e}")
    finally:
        UserState.set_mode(user_id, "")
        context.user_data.clear()
        parser.clear_data()
