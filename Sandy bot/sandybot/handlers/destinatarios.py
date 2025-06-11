"""Manejo de destinatarios para envíos de SandyBot"""

from telegram import Update
from telegram.ext import ContextTypes
from ..utils import obtener_mensaje
from ..registrador import responder_registrando
from ..database import SessionLocal, Cliente, obtener_cliente_por_nombre

ARCH_KEY = "destinatarios"


async def agregar_destinatario(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Agrega un destinatario para un cliente en la base"""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "agregar_destinatario",
            "Usá: /agregar_destinatario <cliente> <correo> [carrier]",
            "destinatarios",
        )
        return
    cliente = context.args[0]
    correo = context.args[1]
    carrier = context.args[2] if len(context.args) > 2 else None
    with SessionLocal() as session:
        cli = obtener_cliente_por_nombre(cliente)
        if not cli:
            cli = Cliente(nombre=cliente)
            session.add(cli)
            session.commit()
            session.refresh(cli)
        if carrier:
            lista = (
                cli.destinatarios_carrier.get(carrier, [])
                if cli.destinatarios_carrier
                else []
            )
        else:
            lista = cli.destinatarios or []
        if correo in lista:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text,
                f"{correo} ya está registrado para {cliente}.",
                "destinatarios",
            )
            return
        lista.append(correo)
        if carrier:
            mapa = cli.destinatarios_carrier or {}
            mapa[carrier] = lista
            cli.destinatarios_carrier = mapa
        else:
            cli.destinatarios = lista
        session.commit()
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text,
        f"Destinatario {correo} agregado para {cliente}.",
        "destinatarios",
    )


async def eliminar_destinatario(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Elimina un destinatario de un cliente"""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "eliminar_destinatario",
            "Usá: /eliminar_destinatario <cliente> <correo> [carrier]",
            "destinatarios",
        )
        return
    cliente = context.args[0]
    correo = context.args[1]
    carrier = context.args[2] if len(context.args) > 2 else None
    with SessionLocal() as session:
        cli = obtener_cliente_por_nombre(cliente)
        if not cli:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text,
                f"{cliente} no existe.",
                "destinatarios",
            )
            return
        if carrier:
            lista = (
                cli.destinatarios_carrier.get(carrier, [])
                if cli.destinatarios_carrier
                else []
            )
        else:
            lista = cli.destinatarios or []
        if correo not in lista:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text,
                f"{correo} no está en la lista de {cliente}.",
                "destinatarios",
            )
            return
        lista = list(lista)
        lista.remove(correo)
        if carrier:
            mapa = cli.destinatarios_carrier or {}
            mapa[carrier] = lista
            cli.destinatarios_carrier = mapa
        else:
            cli.destinatarios = lista
        session.commit()
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text,
        f"Destinatario {correo} eliminado de {cliente}.",
        "destinatarios",
    )


async def listar_destinatarios(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra los destinatarios guardados"""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "listar_destinatarios",
            "Indicá el nombre del cliente y opcionalmente el carrier.",
            "destinatarios",
        )
        return
    cliente = context.args[0]
    carrier = context.args[1] if len(context.args) > 1 else None
    with SessionLocal() as session:
        cli = obtener_cliente_por_nombre(cliente)
        if carrier and cli and cli.destinatarios_carrier:
            lista = cli.destinatarios_carrier.get(carrier, [])
        else:
            lista = cli.destinatarios if cli and cli.destinatarios else []
    if not lista:
        respuesta = f"No hay destinatarios registrados para {cliente}."
    else:
        respuesta = f"Destinatarios de {cliente}:\n" + "\n".join(
            f"- {d}" for d in lista
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "listar_destinatarios",
        respuesta,
        "destinatarios",
    )
