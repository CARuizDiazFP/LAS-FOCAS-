"""
Handler para la verificación de ingresos.
"""
from telegram import Update
from telegram.ext import ContextTypes
import logging
import os
import tempfile
import json
import re
from sandybot.utils import obtener_mensaje
from ..database import obtener_servicio, actualizar_tracking, crear_servicio
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


async def verificar_camara(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Busca servicios por nombre de cámara y responde con las coincidencias."""
    mensaje = obtener_mensaje(update)
    if not mensaje or not mensaje.text:
        logger.warning("No se recibió un nombre de cámara en verificar_camara.")
        return

    nombre_camara = mensaje.text.strip()
    from ..database import buscar_servicios_por_camara

    servicios = buscar_servicios_por_camara(nombre_camara)

    if not servicios:
        await mensaje.reply_text("No encontré servicios con esa cámara.")
        return

    if len(servicios) == 1:
        s = servicios[0]
        await mensaje.reply_text(f"La cámara pertenece al servicio {s.id}: {s.nombre or 'Sin nombre'}")
    else:
        listado = "\n".join(f"{s.id}: {s.nombre or 'Sin nombre'}" for s in servicios)
        await mensaje.reply_text("La cámara figura en varios servicios:\n" + listado)

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

        # El mensaje proviene de un callback, por lo que ``from_user`` apunta
        # al bot. Usamos ``update.effective_user`` para registrar el modo en el
        # usuario correcto.
        user_id = update.effective_user.id
        UserState.set_mode(user_id, "ingresos")
        context.user_data.clear()

        await mensaje.reply_text(
            "Iniciando verificación de ingresos. "
            "Enviá el nombre de la cámara que querés verificar."
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
            servicio = crear_servicio(id=int(id_servicio))
            await mensaje.reply_text(
                f"Servicio {id_servicio} creado en la base de datos."
            )

        try:
            camaras_servicio = json.loads(servicio.camaras) if servicio.camaras else []
        except json.JSONDecodeError:
            camaras_servicio = []

        # Mapas en minúsculas para comparar sin distinguir mayúsculas o minúsculas
        map_archivo = {c.lower(): c for c in camaras_archivo}
        map_servicio = {c.lower(): c for c in camaras_servicio}

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
                        otras_botellas.append(f"{map_servicio[serv_key]} {match.group(0).title()}")
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

        await mensaje.reply_text("\n".join(respuesta))

        actualizar_tracking(int(id_servicio), trackings_txt=[str(destino)])

        UserState.set_mode(user_id, "")
        context.user_data.pop("id_servicio", None)
    except Exception as e:
        await mensaje.reply_text(f"Error al procesar ingresos: {e}")

