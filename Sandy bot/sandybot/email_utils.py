
"""Funciones para enviar archivos por correo."""

from pathlib import Path
import logging
import smtplib
import os
from email.message import EmailMessage

from .config import config
from .utils import cargar_json, guardar_json

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
        smtp_user = getattr(config, "SMTP_USER", os.getenv("SMTP_USER"))
        smtp_pass = getattr(config, "SMTP_PASSWORD", os.getenv("SMTP_PASSWORD"))
        from_addr = getattr(config, "EMAIL_FROM", smtp_user)
        host = getattr(config, "SMTP_HOST", os.getenv("SMTP_HOST", "localhost"))
        port = int(getattr(config, "SMTP_PORT", os.getenv("SMTP_PORT", 25)))
        use_tls = getattr(config, "SMTP_USE_TLS", True)

        msg["From"] = from_addr
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

        if use_tls:
            server = smtplib.SMTP(host, port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(host, port)

        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:  # pragma: no cover - errores dependen del entorno
        logger.error("Error enviando correo: %s", e)
        return False


def cargar_destinatarios(ruta: Path) -> list[str]:
    """Devuelve la lista de correos almacenados en ``ruta``.

    El archivo JSON debe contener una clave ``"emails"`` con una lista de
    direcciones.  Si el archivo no existe se devuelve una lista vacía.
    """
    datos = cargar_json(ruta)
    return datos.get("emails", [])


def agregar_destinatario(correo: str, ruta: Path) -> bool:
    """Agrega ``correo`` a la lista de destinatarios almacenada en ``ruta``."""
    correos = cargar_destinatarios(ruta)
    if correo in correos:
        return True
    correos.append(correo)
    return guardar_json({"emails": correos}, ruta)


def eliminar_destinatario(correo: str, ruta: Path) -> bool:
    """Elimina ``correo`` de la lista guardada en ``ruta``."""
    correos = cargar_destinatarios(ruta)
    if correo not in correos:
        return True
    correos.remove(correo)
    return guardar_json({"emails": correos}, ruta)


def enviar_correo(asunto: str, cuerpo: str, ruta_json: Path, *, host=None, port=None) -> bool:
    """Envía un correo de texto a todos los destinatarios registrados.

    Parameters
    ----------
    asunto: str
        Título del mensaje.
    cuerpo: str
        Contenido principal del mensaje.
    ruta_json: Path
        Ruta al archivo con los destinatarios.
    host: str, optional
        Servidor SMTP a utilizar.  Si no se indica se toma de la configuración
        o ``localhost`` como último recurso.
    port: int, optional
        Puerto del servidor SMTP.  Si se omite se toma de la configuración o
        ``25`` por defecto.
    """

    destinos = cargar_destinatarios(ruta_json)
    if not destinos:
        logger.warning("No se encontraron destinatarios en %s", ruta_json)
        return False

    remitente = getattr(config, "EMAIL_FROM", "bot@example.com")
    host = host or getattr(config, "SMTP_HOST", "localhost")
    port = int(port or getattr(config, "SMTP_PORT", 25))

    mensaje = f"Subject: {asunto}\nFrom: {remitente}\n\n{cuerpo}"

    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.set_debuglevel(1)
            smtp.sendmail(remitente, destinos, mensaje)
        return True
    except Exception as e:  # pragma: no cover - entorno depende del sistema
        logger.error("Error enviando correo: %s", e)
        return False
