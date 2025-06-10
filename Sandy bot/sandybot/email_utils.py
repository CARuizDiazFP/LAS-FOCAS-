
"""Funciones para enviar archivos por correo."""

from pathlib import Path
import json
import logging
import json
import smtplib
import os
from email.message import EmailMessage

from .config import config
from .utils import cargar_json, guardar_json

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
