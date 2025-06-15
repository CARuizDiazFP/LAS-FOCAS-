# Nombre de archivo: reenviar_aviso.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/reenviar_aviso.py
# User-provided custom instructions
import tempfile
import os
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from ..registrador import responder_registrando
from ..database import (
    TareaProgramada,
    TareaServicio,
    Servicio,
    Cliente,
    Carrier,
    SessionLocal,
    obtener_cliente_por_nombre,
)
from ..email_utils import generar_archivo_msg, enviar_correo


async def reenviar_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reenvía el aviso generado para una tarea programada."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return

    user_id = update.effective_user.id
    if not context.args or not context.args[0].isdigit():
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "reenviar_aviso",
            "Usá: /reenviar_aviso <id_tarea> [carrier]",
            "tareas",
        )
        return

    tarea_id = int(context.args[0])
    carrier_nombre = context.args[1] if len(context.args) > 1 else None

    with SessionLocal() as session:
        tarea = session.get(TareaProgramada, tarea_id)
        if not tarea:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text or "reenviar_aviso",
                f"No existe la tarea {tarea_id}.",
                "tareas",
            )
            return

        rels = (
            session.query(TareaServicio)
            .filter(TareaServicio.tarea_id == tarea.id)
            .all()
        )
        servicios = [session.get(Servicio, r.servicio_id) for r in rels]

        cliente = None
        for s in servicios:
            if not s:
                continue
            if s.cliente_id:
                cli = session.get(Cliente, s.cliente_id)
            else:
                cli = obtener_cliente_por_nombre(s.cliente)
            if cli:
                cliente = cli
                break
        if not cliente:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text or "reenviar_aviso",
                "No pude determinar el cliente asociado.",
                "tareas",
            )
            return

        carrier = None
        if carrier_nombre:
            carrier = (
                session.query(Carrier).filter(Carrier.nombre == carrier_nombre).first()
            )
        elif tarea.carrier_id:
            carrier = session.get(Carrier, tarea.carrier_id)
        if not carrier:
            ids = {s.carrier_id for s in servicios if s and s.carrier_id}
            if len(ids) == 1:
                carrier = session.get(Carrier, ids.pop())

        nombre_arch = f"tarea_{tarea.id}.msg"
        ruta_path = Path(tempfile.gettempdir()) / nombre_arch
        _, cuerpo = generar_archivo_msg(
            tarea,
            cliente,
            [s for s in servicios if s],
            str(ruta_path),
            carrier,
        )
        enviar_correo(
            f"Aviso de tarea programada - {cliente.nombre}",
            cuerpo,
            cliente.id,
            carrier.nombre if carrier else None,
        )

        if ruta_path.exists():
            with open(ruta_path, "rb") as f:
                await mensaje.reply_document(f, filename=nombre_arch)
            os.remove(ruta_path)

    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "reenviar_aviso",
        f"Aviso {tarea_id} reenviado.",
        "tareas",
    )
