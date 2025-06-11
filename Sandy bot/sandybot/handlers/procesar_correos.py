"""Procesamiento masivo de correos .msg para registrar tareas."""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

try:
    import extract_msg
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "No se encontró la librería 'extract-msg'. Instalala para usar "/
        "procesar_correos'."
    ) from exc

from ..utils import obtener_mensaje
from ..gpt_handler import gpt
from ..database import (
    crear_tarea_programada,
    obtener_cliente_por_nombre,
    Cliente,
    Servicio,
    Carrier,
    SessionLocal,
)
from ..email_utils import generar_archivo_msg, enviar_correo
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
    if not mensaje or not mensaje.document:
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
    docs = [mensaje.document]
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
            prompt = (
                "Extraé del siguiente correo los datos de la ventana de mantenimiento "
                "y devolvé solo un JSON con las claves 'inicio', 'fin', 'tipo', "
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
                    "ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["inicio", "fin", "tipo", "ids"],
            }
            resp = await gpt.consultar_gpt(prompt)
            datos = await gpt.procesar_json_response(resp, esquema)
            if not datos:
                raise ValueError("JSON inválido")
            inicio = datetime.fromisoformat(str(datos["inicio"]))
            fin = datetime.fromisoformat(str(datos["fin"]))
            tipo = datos["tipo"]
            ids = [int(i) for i in datos.get("ids", [])]
            afect = datos.get("afectacion")
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

            tarea = crear_tarea_programada(
                inicio,
                fin,
                tipo,
                ids,
                carrier_id=carrier.id if carrier else None,
                tiempo_afectacion=afect,
            )
            servicios = [session.get(Servicio, i) for i in ids]
            if carrier:
                for s in servicios:
                    if s:
                        s.carrier_id = carrier.id
                        s.carrier = carrier.nombre
                session.commit()

            nombre_arch = f"tarea_{tarea.id}.msg"
            ruta_msg = Path(tempfile.gettempdir()) / nombre_arch
            generar_archivo_msg(tarea, cliente, [s for s in servicios if s], str(ruta_msg))

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

            if ruta_msg.exists():
                with open(ruta_msg, "rb") as f:
                    await mensaje.reply_document(f, filename=nombre_arch)
        tareas.append(str(tarea.id))

    if tareas:
        await responder_registrando(
            mensaje,
            user_id,
            getattr(mensaje.document, "file_name", ""),
            f"Tareas registradas: {', '.join(tareas)}",
            "tareas",
        )
