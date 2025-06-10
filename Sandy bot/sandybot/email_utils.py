
"""Funciones para enviar archivos por correo."""

from pathlib import Path
import logging
import json
import smtplib
from email.message import EmailMessage

from .config import config

logger = logging.getLogger(__name__)


def cargar_destinatarios(ruta: Path) -> list[str]:
    """Lee un JSON con una lista de correos."""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, list) else datos.get("emails", [])
    except FileNotFoundError:
        return []
    except Exception as e:  # pragma: no cover - solo logging
        logger.error("Error al leer %s: %s", ruta, e)
        return []


def guardar_destinatarios(destinatarios: list[str], ruta: Path) -> bool:
    """Guarda la lista de correos en formato JSON."""
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(destinatarios, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:  # pragma: no cover - solo logging
        logger.error("Error al guardar %s: %s", ruta, e)
        return False


def agregar_destinatario(correo: str, ruta: Path) -> bool:
    lista = cargar_destinatarios(ruta)
    if correo not in lista:
        lista.append(correo)
    return guardar_destinatarios(lista, ruta)


def eliminar_destinatario(correo: str, ruta: Path) -> bool:
    lista = cargar_destinatarios(ruta)
    if correo in lista:
        lista.remove(correo)
    return guardar_destinatarios(lista, ruta)


def enviar_correo(asunto: str, cuerpo: str, ruta_dest: Path, *, host: str = None, port: int = None) -> bool:
    """Envía un correo simple a los destinatarios almacenados."""
    correos = cargar_destinatarios(ruta_dest)
    if not correos:
        return False

    host = host or config.SMTP_HOST
    port = port or config.SMTP_PORT

    msg = f"Subject: {asunto}\n\n{cuerpo}"
    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.set_debuglevel(1)
            smtp.sendmail(config.EMAIL_FROM or config.SMTP_USER, correos, msg)
        return True
    except Exception as e:  # pragma: no cover - depende del entorno
        logger.error("Error enviando correo: %s", e)
        return False


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
