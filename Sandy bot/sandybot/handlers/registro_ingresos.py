# + Nombre de archivo: registro_ingresos.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/registro_ingresos.py
# User-provided custom instructions
"""Flujo para registrar ingresos a cámaras"""
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from .estado import UserState
from ..registrador import responder_registrando
from ..database import crear_ingreso

async def iniciar_registro_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia la carga solicitando ID de servicio."""
    mensaje = update.callback_query.message if update.callback_query else update.message
    user_id = update.effective_user.id
    UserState.set_mode(user_id, "registro_ingresos")
    context.user_data.clear()
    await responder_registrando(
        mensaje,
        user_id,
        "registro_ingresos",
        "Ingresá el ID del servicio al que pertenece la cámara.",
        "registro_ingresos",
    )

async def guardar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda el ingreso paso a paso."""
    mensaje = update.message
    user_id = mensaje.from_user.id

    if "id_servicio" not in context.user_data:
        if mensaje.text and mensaje.text.isdigit():
            context.user_data["id_servicio"] = int(mensaje.text)
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text,
                "Escribí el nombre de la cámara.",
                "registro_ingresos",
            )
        else:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text or "",
                "Indicá un ID numérico de servicio.",
                "registro_ingresos",
            )
        return

    if "camara" not in context.user_data:
        context.user_data["camara"] = mensaje.text.strip()
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text,
            "Indicá la hora en formato HH:MM o la fecha completa AAAA-MM-DD HH:MM.",
            "registro_ingresos",
        )
        return

    if "fecha" not in context.user_data:
        texto = mensaje.text.strip()
        try:
            if " " in texto:
                fecha = datetime.strptime(texto, "%Y-%m-%d %H:%M")
            else:
                hoy = datetime.now().strftime("%Y-%m-%d")
                fecha = datetime.strptime(f"{hoy} {texto}", "%Y-%m-%d %H:%M")
        except ValueError:
            await responder_registrando(
                mensaje,
                user_id,
                mensaje.text,
                "Formato inválido. Usá HH:MM o AAAA-MM-DD HH:MM.",
                "registro_ingresos",
            )
            return

        context.user_data["fecha"] = fecha
        crear_ingreso(
            id_servicio=context.user_data["id_servicio"],
            camara=context.user_data["camara"],
            fecha=fecha,
            usuario=str(user_id),
        )
        UserState.set_mode(user_id, "")
        context.user_data.clear()
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text,
            "Ingreso registrado correctamente.",
            "registro_ingresos",
        )
        return
