"""Detección automática de tareas programadas desde correos."""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from ..gpt_handler import gpt
from ..database import (
    crear_tarea_programada,
    obtener_cliente_por_nombre,
    Cliente,
    Servicio,
    SessionLocal,
)
from ..email_utils import generar_archivo_msg
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)


async def detectar_tarea_mail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa un correo enviado por Telegram y registra la tarea."""

    mensaje = obtener_mensaje(update)
    if not mensaje:
        return

    user_id = update.effective_user.id

    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "detectar_tarea_mail",
            "Usá: /detectar_tarea <cliente> y pegá el correo o adjuntalo como archivo.",
            "tareas",
        )
        return

    cliente_nombre = context.args[0]

    contenido = ""
    if mensaje.document:
        archivo = await mensaje.document.get_file()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await archivo.download_to_drive(tmp.name)
            ruta = tmp.name
        try:
            contenido = Path(ruta).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error("Error leyendo adjunto: %s", e)
            os.remove(ruta)
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.document.file_name,
                "No pude leer el archivo adjunto.",
                "tareas",
            )
            return
        finally:
            os.remove(ruta)
    else:
        partes = mensaje.text.split(maxsplit=2)
        if len(partes) < 3:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text or "detectar_tarea_mail",
                "Pegá el correo completo después del nombre del cliente.",
                "tareas",
            )
            return
        contenido = partes[2]

    prompt = (
        "Extraé del siguiente correo los datos de la ventana de mantenimiento y "
        "devolvé solo un JSON con las claves 'inicio', 'fin', 'tipo', "
        "'afectacion' e 'ids' (lista de servicios).\n\n"
        f"Correo:\n{contenido}"
    )

    esquema = {
        "type": "object",
        "properties": {
            "inicio": {"type": "string"},
            "fin": {"type": "string"},
            "tipo": {"type": "string"},
            "afectacion": {"type": "string"},
            "ids": {
                "type": "array",
                "items": {"type": "integer"},
            },
        },
        "required": ["inicio", "fin", "tipo", "ids"],
    }

    try:
        respuesta = await gpt.consultar_gpt(prompt)
        datos = await gpt.procesar_json_response(respuesta, esquema)
        if not datos:
            raise ValueError("JSON inválido")
    except Exception as e:
        logger.error("Fallo detectando tarea: %s", e)
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or getattr(mensaje.document, "file_name", ""),
            "No pude identificar la tarea en el correo.",
            "tareas",
        )
        return

    try:
        inicio = datetime.fromisoformat(str(datos["inicio"]))
        fin = datetime.fromisoformat(str(datos["fin"]))
    except Exception:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or getattr(mensaje.document, "file_name", ""),
            "Fechas con formato inválido en el correo.",
            "tareas",
        )
        return

    tipo = datos["tipo"]
    ids = [int(i) for i in datos.get("ids", [])]
    afectacion = datos.get("afectacion")

    with SessionLocal() as session:
        cliente = obtener_cliente_por_nombre(cliente_nombre)
        if not cliente:
            cliente = Cliente(nombre=cliente_nombre)
            session.add(cliente)
            session.commit()
            session.refresh(cliente)

        tarea = crear_tarea_programada(inicio, fin, tipo, ids, tiempo_afectacion=afectacion)
        servicios = [session.get(Servicio, i) for i in ids]

        nombre_arch = f"tarea_{tarea.id}.msg"
        ruta = Path(tempfile.gettempdir()) / nombre_arch
        generar_archivo_msg(tarea, cliente, [s for s in servicios if s], str(ruta))

        if ruta.exists():
            with open(ruta, "rb") as f:
                await mensaje.reply_document(f, filename=nombre_arch)

    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or getattr(mensaje.document, "file_name", ""),
        f"Tarea {tarea.id} registrada.",
        "tareas",
    )
