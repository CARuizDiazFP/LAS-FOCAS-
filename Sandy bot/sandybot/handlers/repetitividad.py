# Repetitividad.py
"""
Handler para la generación de informes de repetitividad.
"""
from telegram import Update
from telegram.ext import ContextTypes
import os
import tempfile
import pandas as pd
from docx import Document
import win32com.client as win32
import pythoncom
import locale
from datetime import datetime
import logging

from sandybot.config import config

# Ruta a la plantilla Word definida en la configuración global
# Permite modificar la ubicación mediante la variable de entorno "PLANTILLA_PATH"
RUTA_PLANTILLA = config.PLANTILLA_PATH

logger = logging.getLogger(__name__)

async def manejar_repetitividad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja la generación de informes de repetitividad.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        if not update.message:
            logger.warning("No se recibió un mensaje en manejar_repetitividad.")
            return

        logger.info("Iniciando manejo de repetitividad para el usuario %s", update.message.from_user.id)
        await update.message.reply_text("Generación de informes de repetitividad en desarrollo.")
    except Exception as e:
        logger.error("Error en manejar_repetitividad: %s", e)
        if update.message:
            await update.message.reply_text(f"Error al generar el informe: {e}")

async def iniciar_repetitividad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Inicia el proceso de generación de informes de repetitividad.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        if not update.message:
            logger.warning("No se recibió un mensaje en iniciar_repetitividad.")
            return

        logger.info("Iniciando repetitividad para el usuario %s", update.message.from_user.id)
        await update.message.reply_text("Iniciando generación de informes de repetitividad. Por favor, espere.")
    except Exception as e:
        logger.error("Error en iniciar_repetitividad: %s", e)
        if update.message:
            await update.message.reply_text(f"Error al iniciar la generación de informes: {e}")

async def procesar_repetitividad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Procesa los datos para generar un informe de repetitividad.

    :param update: Objeto de actualización de Telegram.
    :param context: Contexto del manejador.
    """
    try:
        if not update.message or not update.message.document:
            await update.message.reply_text("😠 ¿Y el archivo? Adjuntá el Excel, por favor. No soy adivino. #DaleCerebro")
            return

        archivo = update.message.document
        if not archivo.file_name.endswith(".xlsx"):
            await update.message.reply_text("🙄 Solo acepto archivos Excel (.xlsx). Mandá bien las cosas. #MeEstásCargando")
            return

        file = await archivo.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
            await file.download_to_drive(tmp_excel.name)

        ruta_salida = generar_informe_y_modificar(tmp_excel.name)
        nombre_final = os.path.basename(ruta_salida)
        with open(ruta_salida, "rb") as docx_file:
            await update.message.reply_document(document=docx_file, filename=nombre_final)

        os.remove(tmp_excel.name)
        os.remove(ruta_salida)

    except Exception as e:
        if update.message:
            await update.message.reply_text(f"💥 Algo falló generando el informe. No sé cómo hacés para romper hasta esto... #LoQueHayQueAguantar")


def generar_informe_y_modificar(ruta_excel):
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

    casos_df = pd.read_excel(ruta_excel)
    columnas_a_conservar_casos = ['Número Reclamo', 'Número Línea', 'Tipo Servicio', 'Nombre Cliente',
                                  'Fecha Inicio Reclamo', 'Fecha Cierre Reclamo', 
                                  'Tipo Solución Reclamo', 'Descripción Solución Reclamo']
    casos_limpio = casos_df[columnas_a_conservar_casos]
    fecha_cierre = pd.to_datetime(casos_limpio['Fecha Cierre Reclamo'].iloc[0])
    mes_actual = fecha_cierre.strftime("%B")
    año_actual = fecha_cierre.strftime("%Y")

    casos_limpio = casos_limpio.copy()
    casos_limpio['Número Línea'] = casos_limpio['Número Línea'].astype(str).str.replace('.0', '', regex=False)
    casos_limpio = casos_limpio.sort_values(by='Número Línea')
    lineas_con_multiples_reclamos = casos_limpio['Número Línea'].value_counts()
    lineas_a_conservar = lineas_con_multiples_reclamos[lineas_con_multiples_reclamos >= 2].index
    casos_filtrados = casos_limpio[casos_limpio['Número Línea'].isin(lineas_a_conservar)]

    doc = Document(RUTA_PLANTILLA)

    for numero_linea, grupo in casos_filtrados.groupby('Número Línea'):
        nombre_cliente = grupo['Nombre Cliente'].iloc[0]
        tipo_servicio = grupo['Tipo Servicio'].iloc[0]
        doc.add_paragraph(f'{tipo_servicio}: {numero_linea} - {nombre_cliente}', style='Heading 1')

        tabla = doc.add_table(rows=1, cols=5, style='Table Grid')
        hdr_cells = tabla.rows[0].cells
        hdr_cells[0].text = 'Reclamo'
        hdr_cells[1].text = 'Tipo Solución Reclamo'
        hdr_cells[2].text = 'Fecha Inicio Reclamo'
        hdr_cells[3].text = 'Fecha Cierre Reclamo'
        hdr_cells[4].text = 'Descripción Solución Reclamo'

        for _, fila in grupo.iterrows():
            fila_cells = tabla.add_row().cells
            fila_cells[0].text = str(fila['Número Reclamo'])
            fila_cells[1].text = fila['Tipo Solución Reclamo']
            fila_cells[2].text = fila['Fecha Inicio Reclamo'].strftime('%d/%m/%Y') if pd.notnull(fila['Fecha Inicio Reclamo']) else ''
            fila_cells[3].text = fila['Fecha Cierre Reclamo'].strftime('%d/%m/%Y') if pd.notnull(fila['Fecha Cierre Reclamo']) else ''
            fila_cells[4].text = fila['Descripción Solución Reclamo']

    nombre_archivo = f"InformeRepetitividad{fecha_cierre.strftime('%m%y')}.docx"
    ruta_docx_generado = os.path.join(tempfile.gettempdir(), nombre_archivo)
    doc.save(ruta_docx_generado)

    modificar_informe_con_pythoncom(ruta_docx_generado, mes_actual, año_actual)
    return ruta_docx_generado


def modificar_informe_con_pythoncom(docx_path, mes_actual, año_actual):
    pythoncom.CoInitialize()
    try:
        word_app = win32.Dispatch("Word.Application")
        word_app.Visible = False
        doc = word_app.Documents.Open(docx_path)

        titulo_dinamico = f"Informe Repetitividad {mes_actual} {año_actual}"

        for shape in doc.Shapes:
            if shape.TextFrame.HasText and "Informe" in shape.TextFrame.TextRange.Text:
                shape.TextFrame.TextRange.Text = titulo_dinamico

        for tabla in doc.Tables:
            for cell in tabla.Rows(1).Cells:
                cell.Shading.BackgroundPatternColor = 12611584

        doc.SaveAs(docx_path)
        doc.Close()
        word_app.Quit()
    except Exception as e:
        logger.error("Error al modificar el documento con COM: %s", e)
    finally:
        pythoncom.CoUninitialize()
