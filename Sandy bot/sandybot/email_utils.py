"""Funciones para el envío de correos electrónicos"""

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional

from .config import config

logger = logging.getLogger(__name__)


def enviar_email(
    destinatarios: Iterable[str],
    asunto: str,
    cuerpo: str,
    adjuntos: Optional[Iterable[str]] = None,
) -> bool:
    """Envía un correo utilizando las credenciales definidas en ``config``.

    Si falta alguna credencial obligatoria se registra un error y se
    devuelve ``False``.
    """

    if not (config.EMAIL_USER and config.EMAIL_PASSWORD and config.EMAIL_FROM):
        logger.error("Credenciales de correo incompletas")
        return False

    mensaje = EmailMessage()
    mensaje["From"] = config.EMAIL_FROM
    mensaje["To"] = ", ".join(destinatarios)
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    if adjuntos:
        for archivo in adjuntos:
            try:
                path = Path(archivo)
                with open(path, "rb") as f:
                    datos = f.read()
                mensaje.add_attachment(
                    datos,
                    maintype="application",
                    subtype="octet-stream",
                    filename=path.name,
                )
            except Exception as e:
                logger.error("Error al adjuntar %s: %s", archivo, e)

    try:
        with smtplib.SMTP_SSL(config.EMAIL_HOST, config.EMAIL_PORT) as smtp:
            smtp.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
            smtp.send_message(mensaje)
        logger.info("\ud83d\udce7 Correo enviado a %s", mensaje["To"])
        return True
    except Exception as e:
        logger.error("Error al enviar correo: %s", e)
        return False
