"""Manejo de destinatarios para envíos de SandyBot"""

from telegram import Update
from telegram.ext import ContextTypes
from ..utils import cargar_json, guardar_json, obtener_mensaje
from ..config import config
from ..registrador import responder_registrando

ARCH_KEY = "destinatarios"

async def agregar_destinatario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Agrega un destinatario al archivo JSON"""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    texto = " ".join(context.args) if context.args else ""
    if not texto:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "agregar_destinatario",
            "Indicá el destinatario después del comando.",
            "destinatarios",
        )
        return
    datos = cargar_json(config.ARCHIVO_DESTINATARIOS)
    lista = datos.get(ARCH_KEY, [])
    if texto in lista:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text,
            f"{texto} ya está registrado.",
            "destinatarios",
        )
        return
    lista.append(texto)
    datos[ARCH_KEY] = lista
    guardar_json(datos, config.ARCHIVO_DESTINATARIOS)
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text,
        f"Destinatario {texto} agregado correctamente.",
        "destinatarios",
    )

async def eliminar_destinatario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina un destinatario del JSON"""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    texto = " ".join(context.args) if context.args else ""
    if not texto:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "eliminar_destinatario",
            "Indicá el destinatario a borrar.",
            "destinatarios",
        )
        return
    datos = cargar_json(config.ARCHIVO_DESTINATARIOS)
    lista = datos.get(ARCH_KEY, [])
    if texto not in lista:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text,
            f"{texto} no está en la lista.",
            "destinatarios",
        )
        return
    lista.remove(texto)
    datos[ARCH_KEY] = lista
    guardar_json(datos, config.ARCHIVO_DESTINATARIOS)
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text,
        f"Destinatario {texto} eliminado.",
        "destinatarios",
    )

async def listar_destinatarios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los destinatarios guardados"""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    datos = cargar_json(config.ARCHIVO_DESTINATARIOS)
    lista = datos.get(ARCH_KEY, [])
    if not lista:
        respuesta = "No hay destinatarios registrados."
    else:
        respuesta = "Destinatarios registrados:\n" + "\n".join(f"- {d}" for d in lista)
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "listar_destinatarios",
        respuesta,
        "destinatarios",
    )
