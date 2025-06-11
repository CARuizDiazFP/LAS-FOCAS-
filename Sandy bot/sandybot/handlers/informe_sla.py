"""Handler para generar informes de SLA."""

from telegram import Update
from telegram.ext import ContextTypes
from docx import Document

from sandybot.config import config
from ..utils import obtener_mensaje
from ..registrador import responder_registrando, registrar_conversacion


async def iniciar_informe_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Indica al usuario que envíe el Excel de datos para el informe."""
    message = obtener_mensaje(update)
    if not message:
        return
    await responder_registrando(
        message,
        update.effective_user.id,
        "informe_sla",
        "Enviá el archivo con los datos para procesar el informe de SLA.",
        "informe_sla",
    )


def generar_informe_sla(path_excel: str) -> str:
    """Crea el documento Word a partir de la plantilla definida en la configuración."""
    doc = Document(config.SLA_PLANTILLA_PATH)
    # Aquí se procesarían los datos del Excel y se completarían tablas o campos
    output = path_excel.replace(".xlsx", "_SLA.docx")
    doc.save(output)
    return output
