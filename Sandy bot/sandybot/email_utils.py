
"""Funciones para enviar archivos por correo."""

from pathlib import Path
import logging
import smtplib
from email.message import EmailMessage

from .config import config

logger = logging.getLogger(__name__)


def enviar_excel_por_correo(destinatario: str, ruta_excel: str, *, asunto: str = "Reporte SandyBot", cuerpo: str = "Adjunto el archivo Excel.") -> bool:
    """Envía un archivo Excel por correo usando la configuración SMTP.

    Parameters
    ----------
    destinatario: str
        Dirección de correo del destinatario.
    ruta_excel: str
        Ruta al archivo Excel a adjuntar.
    asunto: str, optional
        Asunto del mensaje.
    cuerpo: str, optional
        Texto del cuerpo del correo.

    Returns
    -------
    bool
        ``True`` si el envío fue exitoso, ``False`` en caso de error.
    """
    try:
        ruta = Path(ruta_excel)
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

        msg = EmailMessage()
        msg["From"] = config.SMTP_USER
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.set_content(cuerpo)

        with open(ruta, "rb") as f:
            datos = f.read()
        msg.add_attachment(
            datos,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=ruta.name,
        )

        if config.SMTP_USE_TLS:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT)

        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:  # pragma: no cover - errores dependen del entorno
        logger.error("Error enviando correo: %s", e)
        return False
