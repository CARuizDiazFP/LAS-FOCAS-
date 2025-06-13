# + Nombre de archivo: ingresos.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/ingresos.py
# User-provided custom instructions
"""
Handler para la verificación de ingresos.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
import os
import tempfile
import json
import re
import pandas as pd
from sandybot.utils import obtener_mensaje, normalizar_camara
from ..database import obtener_servicio, actualizar_tracking, crear_servicio
from ..config import config
import shutil
from .estado import UserState
from ..registrador import responder_registrando

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
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            mensaje.text or "manejar_ingresos",
            "Verificación de ingresos en desarrollo.",
            "ingresos",
        )
    except Exception as e:
        await responder_registrando(
            mensaje,
            mensaje.from_user.id if mensaje else update.effective_user.id,
            mensaje.text if mensaje else "manejar_ingresos",
            f"Error al verificar ingresos: {e}",
            "ingresos",
        )


async def verificar_camara(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Busca servicios por nombre de cámara y responde con las coincidencias."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.text:
        logger.warning("No se recibió un nombre de cámara en verificar_camara.")
        return

    nombre_camara = mensaje.text.strip()
    exacto = False
    if (
        (nombre_camara.startswith("'") and nombre_camara.endswith("'"))
        or (nombre_camara.startswith('"') and nombre_camara.endswith('"'))
    ):
        nombre_camara = nombre_camara[1:-1]
        exacto = True

    from ..database import buscar_servicios_por_camara

    servicios = buscar_servicios_por_camara(nombre_camara, exacto=exacto)

    if not servicios:
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            nombre_camara,
            "No encontré servicios con esa cámara.",
            "ingresos",
        )
        return

    if len(servicios) == 1:
        s = servicios[0]
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            nombre_camara,
            f"La cámara pertenece al servicio {s.id}: {s.nombre or 'Sin nombre'}",
            "ingresos",
        )
    else:
        listado = "\n".join(f"{s.id}: {s.nombre or 'Sin nombre'}" for s in servicios)
        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            nombre_camara,
            "La cámara figura en varios servicios:\n" + listado,
            "ingresos",
        )


async def opcion_por_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configura la verificación por nombre de cámara."""
    mensaje = obtener_mensaje(update)
    user_id = update.effective_user.id
    context.user_data["esperando_opcion"] = False
    context.user_data["opcion_ingresos"] = "nombre"
    await responder_registrando(
        mensaje,
        user_id,
        "ingresos_nombre",
        "Enviá el nombre de la cámara que querés verificar.",
        "ingresos",
    )


async def opcion_por_excel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configura la verificación a partir de un Excel con cámaras."""
    mensaje = obtener_mensaje(update)
    user_id = update.effective_user.id
    context.user_data["esperando_opcion"] = False
    context.user_data["opcion_ingresos"] = "excel"
    context.user_data["esperando_archivo_excel"] = True
    await responder_registrando(
        mensaje,
        user_id,
        "ingresos_excel",
        "Adjuntá el Excel con las cámaras en la columna A.",
        "ingresos",
    )


async def iniciar_verificacion_ingresos(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
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

        # El mensaje proviene de un callback, por lo que ``from_user`` apunta
        # al bot. Usamos ``update.effective_user`` para registrar el modo en el
        # usuario correcto.
        user_id = update.effective_user.id
        UserState.set_mode(user_id, "ingresos")
        context.user_data.clear()
        context.user_data["esperando_opcion"] = True

        keyboard = [
            [
                InlineKeyboardButton(
                    "Por nombre de cámara", callback_data="ingresos_nombre"
                ),
                InlineKeyboardButton("Con Excel", callback_data="ingresos_excel"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await responder_registrando(
            mensaje,
            user_id,
            "verificar_ingresos",
            "¿Cómo querés validar las cámaras?",
            "ingresos",
            reply_markup=reply_markup,
        )
    except Exception as e:
        await responder_registrando(
            mensaje,
            user_id,
            "verificar_ingresos",
            f"Error al iniciar la verificación de ingresos: {e}",
            "ingresos",
        )


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
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.caption or mensaje.document.file_name,
                "Primero indicá el ID del servicio en un mensaje de texto.",
                "ingresos",
            )
            return

        documento = mensaje.document
        if not documento.file_name.endswith(".txt"):
            await responder_registrando(
                mensaje,
                user_id,
                documento.file_name,
                "Solo acepto archivos .txt para verificar ingresos.",
                "ingresos",
            )
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
            servicio = crear_servicio(id=int(id_servicio))
            await responder_registrando(
                mensaje,
                user_id,
                documento.file_name,
                f"Servicio {id_servicio} creado en la base de datos.",
                "ingresos",
            )

        camaras_servicio = servicio.camaras or []

        # Mapas normalizados para comparar sin acentos ni mayúsculas
        map_archivo = {normalizar_camara(c): c for c in camaras_archivo}
        map_servicio = {normalizar_camara(c): c for c in camaras_servicio}

        set_archivo = set(map_archivo.keys())
        set_servicio = set(map_servicio.keys())

        # Cálculo de coincidencias y diferencias ignorando mayúsculas
        coinciden_keys = set_archivo & set_servicio
        faltan_keys = set_servicio - set_archivo
        adicionales_keys = set_archivo - set_servicio

        coinciden = sorted(map_servicio[k] for k in coinciden_keys)
        faltantes = sorted(map_servicio[k] for k in faltan_keys)
        adicionales = sorted(map_archivo[k] for k in adicionales_keys)

        # Detección de accesos a otras botellas de la misma cámara
        otras_botellas = []
        for key in adicionales_keys:
            for serv_key in set_servicio:
                if key.startswith(serv_key) and re.search(r"bot\s*\d+", key, re.I):
                    match = re.search(r"bot\s*\d+", map_archivo[key], re.I)
                    if match:
                        otras_botellas.append(
                            f"{map_servicio[serv_key]} {match.group(0).title()}"
                        )
                        break

        # Remover de adicionales los elementos identificados como otras botellas
        adicionales = [a for a in adicionales if a not in otras_botellas]

        respuesta = ["📋 Resultado de la verificación:"]
        if coinciden:
            respuesta.append("✅ Coinciden: " + ", ".join(coinciden))
        if faltantes:
            respuesta.append("❌ Faltan en archivo: " + ", ".join(faltantes))
        if adicionales:
            respuesta.append("⚠️ No esperadas: " + ", ".join(adicionales))
        if otras_botellas:
            respuesta.append(
                "ℹ️ También se detectaron accesos a otras botellas: "
                + ", ".join(otras_botellas)
            )
        if len(respuesta) == 1:
            respuesta.append("No se detectaron cámaras para comparar.")

        await responder_registrando(
            mensaje,
            user_id,
            documento.file_name,
            "\n".join(respuesta),
            "ingresos",
        )

        actualizar_tracking(
            int(id_servicio),
            trackings_txt=[str(destino)],
            tipo="complementario",
        )

        UserState.set_mode(user_id, "")
        context.user_data.pop("id_servicio", None)
    except Exception as e:
        await responder_registrando(
            mensaje,
            user_id if "user_id" in locals() else update.effective_user.id,
            "procesar_ingresos",
            f"Error al procesar ingresos: {e}",
            "ingresos",
        )


async def procesar_ingresos_excel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Procesa un Excel con un listado de cámaras en la columna A."""
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje or not mensaje.document:
            logger.warning("No se recibió un Excel en procesar_ingresos_excel.")
            return

        documento = mensaje.document
        if not documento.file_name.endswith(".xlsx"):
            await responder_registrando(
                mensaje,
                mensaje.from_user.id,
                documento.file_name,
                "Solo acepto archivos Excel (.xlsx).",
                "ingresos",
            )
            return

        archivo = await documento.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            await archivo.download_to_drive(tmp.name)

        try:
            df = pd.read_excel(tmp.name, header=None)
            camaras = [str(c).strip() for c in df.iloc[:, 0].dropna()]
        except Exception as e:
            logger.error("Error leyendo Excel: %s", e)
            await responder_registrando(
                mensaje,
                mensaje.from_user.id,
                documento.file_name,
                "No pude leer el Excel. Verificá el formato.",
                "ingresos",
            )
            os.remove(tmp.name)
            return

        os.remove(tmp.name)

        from ..database import buscar_servicios_por_camara

        lineas = []
        for cam in camaras:
            exacto = False
            texto = cam
            if (
                (texto.startswith("'") and texto.endswith("'"))
                or (texto.startswith('"') and texto.endswith('"'))
            ):
                texto = texto[1:-1]
                exacto = True
            servicios = buscar_servicios_por_camara(texto, exacto=exacto)
            if not servicios:
                lineas.append(f"{cam}: sin coincidencias")
            elif len(servicios) == 1:
                s = servicios[0]
                nombre = s.nombre or "Sin nombre"
                lineas.append(f"{cam}: {s.id} - {nombre}")
            else:
                ids = ", ".join(str(s.id) for s in servicios)
                lineas.append(f"{cam}: varios servicios ({ids})")

        respuesta = (
            "\n".join(lineas)
            if lineas
            else "No se encontraron cámaras en la columna A."
        )

        await responder_registrando(
            mensaje,
            mensaje.from_user.id,
            documento.file_name,
            respuesta,
            "ingresos",
        )

        UserState.set_mode(mensaje.from_user.id, "")
        context.user_data.clear()
    except Exception as e:
        await responder_registrando(
            mensaje,
            mensaje.from_user.id if mensaje else update.effective_user.id,
            "procesar_ingresos_excel",
            f"Error al procesar el Excel: {e}",
            "ingresos",
        )
