"""
Handler para la comparación de trazados de fibra óptica.
"""
from telegram import Update
from telegram.ext import ContextTypes
from typing import List
import logging
from sandybot.utils import normalizar_texto, obtener_mensaje

logger = logging.getLogger(__name__)

async def iniciar_comparador(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Inicia el proceso de comparación de trazados de fibra óptica.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en iniciar_comparador.")
            return

        await mensaje.reply_text(
            "Iniciando comparación de trazados de fibra óptica. Por favor, envíe los datos necesarios."
        )
    except Exception as e:
        await mensaje.reply_text(f"Error al iniciar la comparación: {e}")

async def manejar_comparacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja la comparación de trazados de fibra óptica.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en manejar_comparacion.")
            return

        # Validar que el usuario haya enviado datos para comparar
        if not mensaje.text:
            await mensaje.reply_text("Por favor, envíe los datos de los trazados a comparar.")
            return

        # Normalizar y procesar los datos de entrada
        datos_entrada: str = normalizar_texto(mensaje.text)
        trazados: List[str] = datos_entrada.split("\n")

        if len(trazados) < 2:
            await mensaje.reply_text("Se necesitan al menos dos trazados para realizar la comparación.")
            return

        # Realizar la comparación (lógica de ejemplo)
        resultados = []
        for i in range(len(trazados) - 1):
            for j in range(i + 1, len(trazados)):
                resultado = f"Comparación entre trazado {i + 1} y {j + 1}: OK"
                resultados.append(resultado)

        # Enviar los resultados al usuario
        mensaje_resultados = "\n".join(resultados)
        await mensaje.reply_text(f"Resultados de la comparación:\n{mensaje_resultados}")

    except Exception as e:
        await mensaje.reply_text(f"Error al procesar la comparación: {e}")

async def recibir_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Recibe y procesa el archivo de tracking enviado por el usuario.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en recibir_tracking.")
            return

        await mensaje.reply_text(
            "Recibiendo archivo de tracking. Por favor, espere mientras se procesa."
        )
    except Exception as e:
        await mensaje.reply_text(f"Error al recibir el archivo de tracking: {e}")

async def procesar_comparacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Procesa los datos enviados para realizar una comparación detallada.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        mensaje = obtener_mensaje(update)
        if not mensaje:
            logger.warning("No se recibió un mensaje en procesar_comparacion.")
            return

        await mensaje.reply_text("Procesando comparación detallada. Por favor, espere.")
    except Exception as e:
        await mensaje.reply_text(f"Error al procesar la comparación: {e}")

