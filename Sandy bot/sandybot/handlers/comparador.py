"""
Handler para la comparación de trazados de fibra óptica.
"""
from telegram import Update
from telegram.ext import ContextTypes
from typing import List
import logging
import os
import tempfile
import pandas as pd
from fuzzywuzzy import fuzz
from sandybot.utils import normalizar_texto, obtener_mensaje
from .estado import UserState

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

        user_id = mensaje.from_user.id
        UserState.set_mode(user_id, "comparador")
        context.user_data["trackings"] = []
        await mensaje.reply_text(
            "Iniciando comparación de trazados de fibra óptica. "
            "Adjuntá los trackings (.txt) y luego enviá /procesar."
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

        await mensaje.reply_text(
            "Los datos enviados serán ignorados. "
            "Adjuntá los archivos y usá /procesar para obtener el Excel."
        )

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
        if not mensaje or not mensaje.document:
            logger.warning("No se recibió un documento en recibir_tracking.")
            return

        documento = mensaje.document
        if not documento.file_name.endswith(".txt"):
            await mensaje.reply_text(
                "🙄 Solo acepto archivos .txt para comparar trazados."
            )
            return

        archivo = await documento.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            await archivo.download_to_drive(tmp.name)

        user_id = mensaje.from_user.id
        UserState.set_tracking(user_id, tmp.name)
        context.user_data.setdefault("trackings", []).append(tmp.name)
        await mensaje.reply_text(
            "📎 Archivo recibido. Podés adjuntar otro o enviar /procesar."
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

        user_id = mensaje.from_user.id
        trackings = context.user_data.get("trackings", [])
        if len(trackings) < 2:
            await mensaje.reply_text(
                "¿Procesar qué? Necesito al menos dos archivos de tracking."
            )
            return

        await mensaje.reply_text("Procesando comparación, aguarde...")

        try:
            # Creamos los dataframes manualmente para evitar problemas con pandas
            # al leer líneas vacías o caracteres especiales. Cada archivo se
            # procesa línea por línea y solo se guardan aquellas no vacías.
            dataframes = []
            for ruta in trackings[:2]:
                with open(ruta, "r", encoding="utf-8") as f:
                    lineas = [line.strip() for line in f if line.strip()]
                dataframes.append(pd.DataFrame(lineas, columns=["camara"]))

            cam1 = dataframes[0]["camara"].astype(str).tolist()
            cam2 = dataframes[1]["camara"].astype(str).tolist()

            resultados = []
            for c1 in cam1:
                mejor_score = 0
                mejor_c2 = ""
                for c2 in cam2:
                    score = fuzz.token_set_ratio(normalizar_texto(c1), normalizar_texto(c2))
                    if score > mejor_score:
                        mejor_score = score
                        mejor_c2 = c2
                resultados.append({
                    "Camara Archivo 1": c1,
                    "Coincidencia Archivo 2": mejor_c2,
                    "Puntaje": mejor_score,
                })

            df_result = pd.DataFrame(resultados)
            salida = os.path.join(tempfile.gettempdir(), f"ComparacionFO_{user_id}.xlsx")
            df_result.to_excel(salida, index=False)

            with open(salida, "rb") as doc:
                await mensaje.reply_document(doc, filename=os.path.basename(salida))

        except Exception as e:
            logger.error("Error generando Excel: %s", e)
            await mensaje.reply_text(f"💥 Algo falló al generar el Excel: {e}")
        finally:
            for ruta in trackings:
                try:
                    os.remove(ruta)
                except OSError:
                    pass
            if 'salida' in locals():
                try:
                    os.remove(salida)
                except OSError:
                    pass
            context.user_data["trackings"] = []
            UserState.set_mode(user_id, "")
    except Exception as e:
        await mensaje.reply_text(f"Error al procesar la comparación: {e}")

