"""Handler para la carga de trackings en la base de datos."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
import re
from pathlib import Path
from datetime import datetime
from ..utils import obtener_mensaje, normalizar_camara
from ..tracking_parser import TrackingParser
from ..config import config
from ..database import actualizar_tracking, obtener_servicio, crear_servicio
from .estado import UserState
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)

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
    await responder_registrando(
        mensaje,
        user_id,
        "cargar_tracking",
        "Enviá el archivo .txt del tracking para comenzar.",
        "cargar_tracking",
    )

async def guardar_tracking_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda el tracking en la base de datos."""
    mensaje = obtener_mensaje(update)
    if not mensaje and not context.user_data.get("tracking_files"):
        return

    user_id = mensaje.from_user.id if mensaje else update.effective_user.id
    documento = mensaje.document if mensaje else None

    # Si llegó un documento, guardarlo temporalmente
    if documento:
        if not documento.file_name.endswith(".txt"):
            await responder_registrando(
                mensaje,
                user_id,
                documento.file_name,
                "Solo acepto archivos .txt para el tracking.",
                "cargar_tracking",
            )
            return

        archivo = await documento.get_file()
        ruta_temp = config.DATA_DIR / f"tmp_{documento.file_unique_id}.txt"
        await archivo.download_to_drive(str(ruta_temp))

        archivos = context.user_data.setdefault("tracking_files", [])
        match = re.search(r"_(\d+)", documento.file_name)
        archivos.append(
            {
                "ruta": str(ruta_temp),
                "id": int(match.group(1)) if match else None,
                "nombre": documento.file_name,
            }
        )

        if len(archivos) > 1:
            await responder_registrando(
                mensaje,
                user_id,
                documento.file_name,
                f"Archivo agregado. Hay {len(archivos)} archivos en cola.",
                "cargar_tracking",
            )
            return

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
            await responder_registrando(
                mensaje,
                user_id,
                documento.file_name,
                f"Se detectó el ID {match.group(1)}. ¿Deseás asociarlo a este servicio?",
                "cargar_tracking",
            )
            await mensaje.reply_text(
                f"Se detectó el ID {match.group(1)}. ¿Deseás asociarlo a este servicio?",
                reply_markup=keyboard,
            )
        else:
            await responder_registrando(
                mensaje,
                user_id,
                documento.file_name,
                "No pude detectar el ID. Escribí el número del servicio.",
                "cargar_tracking",
            )
        context.user_data["confirmar_id"] = True
        return

    servicio = context.user_data.get("id_servicio")
    archivos = context.user_data.get("tracking_files", [])
    ruta_temp = archivos[0]["ruta"] if archivos else None
    if servicio is None or ruta_temp is None:
        await responder_registrando(
            mensaje,
            user_id,
            "guardar_tracking",
            "Falta el ID o el archivo de tracking.",
            "cargar_tracking",
        )
        return

    if "tipo_tracking" not in context.user_data:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Principal", callback_data="tracking_principal"),
                    InlineKeyboardButton(
                        "Complementario", callback_data="tracking_complementario"
                    ),
                ]
            ]
        )
        await responder_registrando(
            mensaje,
            user_id,
            "seleccionar_tipo",
            "Seleccioná el tipo del tracking.",
            "cargar_tracking",
        )
        await mensaje.reply_text("¿El tracking es principal o complementario?", reply_markup=keyboard)
        return

    ruta_destino = config.DATA_DIR / f"tracking_{servicio}.txt"
    rutas_extra = []
    if ruta_destino.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        historico = config.HISTORICO_DIR / f"tracking_{servicio}_{timestamp}.txt"
        ruta_destino.rename(historico)
        rutas_extra.append(str(historico))

    Path(ruta_temp).rename(ruta_destino)

    parser = TrackingParser()
    try:
        parser.clear_data()
        parser.parse_file(str(ruta_destino))
        camaras = parser._data[0][1]["camara"].astype(str).tolist()
        rutas_extra.append(str(ruta_destino))
        id_servicio = int(servicio)
        existente = obtener_servicio(id_servicio)
        if not existente:
            crear_servicio(id=id_servicio)
            cam_anterior = []
        else:
            cam_anterior = existente.camaras or []

        nuevas = {normalizar_camara(c) for c in camaras}
        anteriores = {normalizar_camara(c) for c in cam_anterior}
        if nuevas == anteriores:
            await responder_registrando(
                mensaje,
                user_id,
                f"tracking_{servicio}.txt",
                "Sin diferencias con el último tracking. Se omitió la carga.",
                "cargar_tracking",
            )
            return

        tipo = context.user_data.pop("tipo_tracking", "principal")
        actualizar_tracking(
            id_servicio,
            str(ruta_destino),
            camaras,
            rutas_extra,
            tipo=tipo,
        )
        await responder_registrando(
            mensaje,
            user_id,
            f"tracking_{servicio}.txt",
            "✅ Tracking cargado y guardado correctamente.",
            "cargar_tracking",
        )
    except Exception as e:
        logger.error("Error al guardar tracking: %s", e)
        await responder_registrando(
            mensaje,
            user_id,
            documento.file_name if documento else "guardar_tracking",
            f"Error al procesar el tracking: {e}",
            "cargar_tracking",
        )
    finally:
        parser.clear_data()

    # Eliminar la ruta procesada y mantener la cola
    if context.user_data.get("tracking_files"):
        context.user_data["tracking_files"].pop(0)
    context.user_data.pop("id_servicio", None)
    context.user_data.pop("id_servicio_detected", None)
    context.user_data.pop("confirmar_id", None)

    if context.user_data.get("tracking_files"):
        siguiente = context.user_data["tracking_files"][0]
        if siguiente.get("id") is not None:
            context.user_data["id_servicio_detected"] = siguiente["id"]
            context.user_data["confirmar_id"] = True
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
            await responder_registrando(
                mensaje,
                user_id,
                siguiente["nombre"],
                f"Se detectó el ID {siguiente['id']}. ¿Deseás asociarlo a este servicio?",
                "cargar_tracking",
            )
            await mensaje.reply_text(
                f"Se detectó el ID {siguiente['id']}. ¿Deseás asociarlo a este servicio?",
                reply_markup=keyboard,
            )
        else:
            context.user_data["confirmar_id"] = True
            await responder_registrando(
                mensaje,
                user_id,
                siguiente["nombre"],
                "No pude detectar el ID. Escribí el número del servicio.",
                "cargar_tracking",
            )
        UserState.set_mode(user_id, "cargar_tracking")
    else:
        UserState.set_mode(user_id, "")
        context.user_data.clear()
