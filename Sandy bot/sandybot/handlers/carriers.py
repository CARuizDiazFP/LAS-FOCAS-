# + Nombre de archivo: carriers.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/carriers.py
# User-provided custom instructions
"""Comandos para administrar carriers."""

from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from ..registrador import responder_registrando
from ..database import SessionLocal, Carrier


async def listar_carriers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los carriers registrados."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    with SessionLocal() as session:
        carriers = session.query(Carrier).order_by(Carrier.nombre).all()
    if not carriers:
        texto = "No hay carriers registrados."
    else:
        texto = "Carriers registrados:\n" + "\n".join(f"- {c.nombre}" for c in carriers)
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "listar_carriers",
        texto,
        "carriers",
    )


async def agregar_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra un carrier de forma manual."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "agregar_carrier",
            "Usá: /agregar_carrier <nombre>",
            "carriers",
        )
        return
    nombre = context.args[0]
    with SessionLocal() as session:
        carrier = session.query(Carrier).filter(Carrier.nombre == nombre).first()
        if carrier:
            texto = f"{nombre} ya existe."
        else:
            carrier = Carrier(nombre=nombre)
            session.add(carrier)
            session.commit()
            texto = f"Carrier {nombre} agregado."
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text,
        texto,
        "carriers",
    )


async def eliminar_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina un carrier dado su nombre."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "eliminar_carrier",
            "Usá: /eliminar_carrier <nombre>",
            "carriers",
        )
        return
    nombre = context.args[0]
    with SessionLocal() as session:
        carrier = session.query(Carrier).filter(Carrier.nombre == nombre).first()
        if not carrier:
            texto = f"{nombre} no existe."
        else:
            session.delete(carrier)
            session.commit()
            texto = f"Carrier {nombre} eliminado."
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text,
        texto,
        "carriers",
    )


async def actualizar_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cambia el nombre de un carrier existente."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "actualizar_carrier",
            "Usá: /actualizar_carrier <nombre_antiguo> <nombre_nuevo>",
            "carriers",
        )
        return
    viejo, nuevo = context.args[0], context.args[1]
    with SessionLocal() as session:
        carrier = session.query(Carrier).filter(Carrier.nombre == viejo).first()
        if not carrier:
            texto = f"{viejo} no existe."
        elif session.query(Carrier).filter(Carrier.nombre == nuevo).first():
            texto = f"Ya existe un carrier llamado {nuevo}."
        else:
            carrier.nombre = nuevo
            session.commit()
            texto = f"Carrier {viejo} actualizado a {nuevo}."
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text,
        texto,
        "carriers",
    )
