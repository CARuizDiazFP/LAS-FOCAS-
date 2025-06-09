import os
import smtplib
from email.message import EmailMessage
import logging
from .config import config

logger = logging.getLogger(__name__)


def enviar_email(destinatarios, asunto, cuerpo, archivo_adjunto):
    """Envía un correo con un adjunto.

    Parameters
    ----------
    destinatarios : list[str]
        Lista de direcciones de correo.
    asunto : str
        Asunto del mensaje.
    cuerpo : str
        Texto del correo.
    archivo_adjunto : str
        Ruta al archivo a adjuntar.

    Returns
    -------
    bool
        ``True`` si el envío fue exitoso.
    """
    if not config.SMTP_HOST or not config.EMAIL_FROM:
        logger.error("Configuración SMTP incompleta")
        return False

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(cuerpo)

    try:
        with open(archivo_adjunto, "rb") as f:
            datos = f.read()
            nombre = os.path.basename(archivo_adjunto)
        msg.add_attachment(datos, maintype="application", subtype="octet-stream", filename=nombre)
    except Exception as e:
        logger.error("No se pudo adjuntar el archivo: %s", e)
        return False

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            if config.SMTP_USER and config.SMTP_PASSWORD:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Correo enviado a %s", destinatarios)
        return True
    except Exception as e:
        logger.error("Error enviando correo: %s", e)
        return False
