# Nombre de archivo: supermenu.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/supermenu.py
# User-provided custom instructions
"""Comandos de acceso rápido para consultas de base."""

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from ..config import config
from ..database import (
    obtener_servicios,
    obtener_reclamos,
    obtener_camaras,
    obtener_clientes,
    obtener_carriers,
    obtener_conversaciones,
    obtener_ingresos,
    obtener_tareas_programadas,
    obtener_tareas_servicio,
    depurar_servicios_duplicados,
    depurar_reclamos_duplicados,
)
from ..utils import obtener_mensaje
from ..registrador import responder_registrando


async def supermenu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra opciones avanzadas si la contraseña coincide."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    if not context.args:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "Supermenu",
            "Usá: /Supermenu <contraseña>",
            "supermenu",
        )
        return
    clave = context.args[0]
    if clave != config.SUPER_PASS:
        await responder_registrando(
            mensaje,
            user_id,
            mensaje.text or "Supermenu",
            "Contraseña incorrecta.",
            "supermenu",
        )
        return
    botones = [[
        "/CDB_Servicios",
        "/CDB_Reclamos",
        "/CDB_Camaras",
        "/Depurar_Duplicados",
        "/CDB_Clientes",
        "/CDB_Carriers",
        "/CDB_Conversaciones",
        "/CDB_Ingresos",
        "/CDB_Tareas",
        "/CDB_TareasServicio",
    ]]
    markup = ReplyKeyboardMarkup(botones, resize_keyboard=True)
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "Supermenu",
        "Seleccioná una opción:",
        "supermenu",
        reply_markup=markup,
    )


async def listar_servicios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enumera los servicios en orden descendente."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    servicios = obtener_servicios(desc=True)
    if not servicios:
        texto = "No hay servicios registrados."
    else:
        texto = "Servicios:\n" + "\n".join(
            f"{i + 1}. {s.id} {s.nombre or ''}" for i, s in enumerate(servicios)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Servicios",
        texto,
        "supermenu",
    )


async def listar_reclamos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los reclamos de forma descendente."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    reclamos = obtener_reclamos(desc=True)
    if not reclamos:
        texto = "No hay reclamos registrados."
    else:
        texto = "Reclamos:\n" + "\n".join(
            f"{i + 1}. {r.numero or 'sin número'}" for i, r in enumerate(reclamos)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Reclamos",
        texto,
        "supermenu",
    )


async def listar_camaras(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista todas las cámaras registradas."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    camaras = obtener_camaras(desc=True)
    if not camaras:
        texto = "No hay cámaras registradas."
    else:
        texto = "Cámaras:\n" + "\n".join(
            f"{i + 1}. {c.nombre}" for i, c in enumerate(camaras)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Camaras",
        texto,
        "supermenu",
    )


async def depurar_duplicados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina registros duplicados de servicios y reclamos."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    elim_serv = depurar_servicios_duplicados()
    elim_rec = depurar_reclamos_duplicados()
    texto = (
        "Depuración completada:\n"
        f"Servicios eliminados: {elim_serv}\n"
        f"Reclamos eliminados: {elim_rec}"
    )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "Depurar_Duplicados",
        texto,
        "supermenu",
    )


async def listar_clientes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los clientes registrados."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    clientes = obtener_clientes(desc=True)
    if not clientes:
        texto = "No hay clientes registrados."
    else:
        texto = "Clientes:\n" + "\n".join(
            f"{i + 1}. {c.nombre}" for i, c in enumerate(clientes)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Clientes",
        texto,
        "supermenu",
    )


async def listar_carriers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enumera los carriers de la base."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    carriers = obtener_carriers(desc=True)
    if not carriers:
        texto = "No hay carriers registrados."
    else:
        texto = "Carriers:\n" + "\n".join(
            f"{i + 1}. {c.nombre}" for i, c in enumerate(carriers)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Carriers",
        texto,
        "supermenu",
    )


async def listar_conversaciones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista las conversaciones guardadas."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    convs = obtener_conversaciones(desc=True)
    if not convs:
        texto = "No hay conversaciones registradas."
    else:
        texto = "Conversaciones:\n" + "\n".join(
            f"{i + 1}. {c.mensaje}" for i, c in enumerate(convs)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Conversaciones",
        texto,
        "supermenu",
    )


async def listar_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los ingresos ordenados por fecha."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    ingresos = obtener_ingresos(desc=True)
    if not ingresos:
        texto = "No hay ingresos registrados."
    else:
        texto = "Ingresos:\n" + "\n".join(
            f"{i + 1}. {ing.camara}" for i, ing in enumerate(ingresos)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Ingresos",
        texto,
        "supermenu",
    )


async def listar_tareas_programadas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Lista las tareas programadas."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    tareas = obtener_tareas_programadas(desc=True)
    if not tareas:
        texto = "No hay tareas programadas."
    else:
        texto = "Tareas:\n" + "\n".join(
            f"{i + 1}. {t.tipo_tarea}" for i, t in enumerate(tareas)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_Tareas",
        texto,
        "supermenu",
    )


async def listar_tareas_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la tabla de relaciones tarea-servicio."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return
    user_id = update.effective_user.id
    rels = obtener_tareas_servicio(servicio_id=None, desc=True)
    if not rels:
        texto = "No hay relaciones registradas."
    else:
        texto = "Tareas-Servicio:\n" + "\n".join(
            f"{i + 1}. {r.tarea_id}-{r.servicio_id}" for i, r in enumerate(rels)
        )
    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "CDB_TareasServicio",
        texto,
        "supermenu",
    )
