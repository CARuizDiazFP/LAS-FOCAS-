# Nombre de archivo: ingresar_tarea.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/ingresar_tarea.py
# User-provided custom instructions
"""Ingreso manual de tareas programadas."""
from telegram import Update
from telegram.ext import ContextTypes

from .tarea_programada import registrar_tarea_programada


async def ingresar_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Alias simplificado a :func:`registrar_tarea_programada`."""
    await registrar_tarea_programada(update, context)
