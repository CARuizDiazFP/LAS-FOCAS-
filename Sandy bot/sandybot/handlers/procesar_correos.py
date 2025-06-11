"""Procesamiento masivo de correos .msg para registrar tareas."""

import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

try:
    import extract_msg
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "No se encontró la librería 'extract-msg'. Instalala para usar "
        / "procesar_correos'."
    ) from exc

from ..utils import obtener_mensaje
from ..database import (
    obtener_cliente_por_nombre,
    Cliente,
    Carrier,
    SessionLocal,
)
from ..email_utils import generar_archivo_msg, enviar_correo, procesar_correo_a_tarea
from ..registrador import responder_registrando

logger = logging.getLogger(__name__)


def _leer_msg(ruta: str) -> str:
    """Devuelve el asunto y cuerpo de un archivo MSG."""
    try:
        msg = extract_msg.Message(ruta)
        asunto = msg.subject or ""
        cuerpo = msg.body or ""
        return f"{asunto}\n{cuerpo}".strip()
    except Exception as exc:  # pragma: no cover - depende del archivo
        logger.error("Error leyendo MSG %s: %s", ruta, exc)
        return ""


async def procesar_correos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analiza uno o varios archivos `.msg` adjuntos y crea las tareas."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return

    user_id = update.effective_user.id

    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or getattr(mensaje.document, "file_name", ""),
            "Usá: /procesar_correos <cliente> [carrier] y adjuntá los archivos.",
            "tareas",
        )
        return

    cliente_nombre = context.args[0]
    carrier_nombre = context.args[1] if len(context.args) > 1 else None

    docs = []
    if getattr(mensaje, "document", None):
        docs.append(mensaje.document)
    docs.extend(getattr(mensaje, "documents", []))
    if not docs:
        return
    first_name = getattr(docs[0], "file_name", "")

    tareas = []

    for doc in docs:
        archivo = await doc.get_file()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await archivo.download_to_drive(tmp.name)
            ruta = tmp.name
        try:
            contenido = _leer_msg(ruta)
            if not contenido:
                raise ValueError("Sin contenido")
        except Exception as e:  # pragma: no cover - manejo simple
            logger.error("Fallo procesando correo: %s", e)
            os.remove(ruta)
            continue
        os.remove(ruta)

        with SessionLocal() as session:
            cliente = obtener_cliente_por_nombre(cliente_nombre)
            if not cliente:
                cliente = Cliente(nombre=cliente_nombre)
                session.add(cliente)
                session.commit()
                session.refresh(cliente)

            carrier = None
            if carrier_nombre:
                carrier = (
                    session.query(Carrier)
                    .filter(Carrier.nombre == carrier_nombre)
                    .first()
                )
                if not carrier:
                    carrier = Carrier(nombre=carrier_nombre)
                    session.add(carrier)
                    session.commit()
                    session.refresh(carrier)

        try:
            tarea, servicios = await procesar_correo_a_tarea(contenido, cliente, carrier)
        except Exception as e:  # pragma: no cover - manejo simple
            logger.error("Fallo procesando correo: %s", e)
            continue

        nombre_arch = f"tarea_{tarea.id}.msg"
        ruta_msg = Path(tempfile.gettempdir()) / nombre_arch
        generar_archivo_msg(tarea, cliente, servicios, str(ruta_msg))

        cuerpo = ""
        try:
            cuerpo = Path(ruta_msg).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
        enviar_correo(
            f"Aviso de tarea programada - {cliente.nombre}",
            cuerpo,
            cliente.id,
        )
        try:
            tarea, servicios = await procesar_correo_a_tarea(contenido, cliente, carrier)
        except Exception as e:  # pragma: no cover - manejo simple
            logger.error("Fallo procesando correo: %s", e)
            continue

        nombre_arch = f"tarea_{tarea.id}.msg"
        ruta_msg = Path(tempfile.gettempdir()) / nombre_arch

        # Generar archivo .MSG (usando servicios válidos)
        generar_archivo_msg(
            tarea,
            cliente,
            [s for s in servicios if s],
            str(ruta_msg)
        )

        # Intentar leer el contenido del archivo (solo para previsualización si falla el envío)
        cuerpo = ""
        try:
            cuerpo = Path(ruta_msg).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

        # Enviar por correo a destinatarios del cliente
        enviar_correo(
            f"Aviso de tarea programada - {cliente.nombre}",
            cuerpo,
            cliente.id,
            carrier.nombre if carrier else None,
        )

        # Enviar archivo .MSG al usuario por Telegram (si existe)
        if ruta_msg.exists():
            with open(ruta_msg, "rb") as f:
                await mensaje.reply_document(f, filename=nombre_arch)

        tareas.append(str(tarea.id))

    if tareas:
        await responder_registrando(
            mensaje,
            user_id,
            first_name,
            f"Tareas registradas: {', '.join(tareas)}",
            "tareas",
        )
