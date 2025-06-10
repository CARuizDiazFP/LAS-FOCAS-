
"""Funciones para enviar archivos por correo."""

from pathlib import Path
import json
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


def cargar_destinatarios(ruta: Path) -> list[str]:
    """Devuelve la lista de destinatarios almacenada en ``ruta``."""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:  # pragma: no cover - errores dependen del entorno
        logger.error("Error al leer destinatarios: %s", e)
        return []


def _guardar_destinatarios(ruta: Path, lista: list[str]) -> bool:
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:  # pragma: no cover - errores dependen del entorno
        logger.error("Error al guardar destinatarios: %s", e)
        return False


def agregar_destinatario(correo: str, ruta: Path) -> bool:
    """Agrega un correo a la lista de destinatarios."""
    lista = cargar_destinatarios(ruta)
    if correo not in lista:
        lista.append(correo)
        return _guardar_destinatarios(ruta, lista)
    return True


def eliminar_destinatario(correo: str, ruta: Path) -> bool:
    """Elimina un correo de la lista de destinatarios."""
    lista = cargar_destinatarios(ruta)
    if correo in lista:
        lista.remove(correo)
        return _guardar_destinatarios(ruta, lista)
    return False


def enviar_correo(asunto: str, cuerpo: str, ruta_destinatarios: Path, *, host: str | None = None, port: int | None = None) -> bool:
    """Envía un correo simple a los destinatarios cargados en un JSON."""
    dests = cargar_destinatarios(ruta_destinatarios)
    if not dests:
        return False
    try:
        with smtplib.SMTP(host or "localhost", port or 25) as server:
            server.set_debuglevel(1)
            server.sendmail(config.EMAIL_FROM or config.SMTP_USER, dests, cuerpo)
        return True
    except Exception as e:  # pragma: no cover - errores dependen del entorno
        logger.error("Error enviando correo: %s", e)
        return False
