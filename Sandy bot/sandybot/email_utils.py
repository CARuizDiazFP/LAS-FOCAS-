
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

        import os
        smtp_user = os.getenv("SMTP_USER", getattr(config, "EMAIL_USER", ""))
        smtp_host = os.getenv("SMTP_HOST", getattr(config, "EMAIL_HOST", ""))
        smtp_port = int(os.getenv("SMTP_PORT", getattr(config, "EMAIL_PORT", 0)))
        smtp_pwd = os.getenv("SMTP_PASSWORD", getattr(config, "EMAIL_PASSWORD", ""))
        use_tls = os.getenv("SMTP_USE_TLS", str(getattr(config, "SMTP_USE_TLS", True))).lower() != "false"

        msg["From"] = smtp_user or getattr(config, "EMAIL_FROM", "")

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

            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        if smtp_user and smtp_pwd:
            server.login(smtp_user, smtp_pwd)

        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:  # pragma: no cover - errores dependen del entorno
        logger.error("Error enviando correo: %s", e)
        return False


def cargar_destinatarios(ruta: str | Path) -> list[str]:
    """Devuelve la lista de correos almacenada en ``ruta``."""
    from .utils import cargar_json

    datos = cargar_json(Path(ruta))
    return datos.get("destinatarios", []) if isinstance(datos, dict) else []


def agregar_destinatario(correo: str, ruta: str | Path) -> bool:
    """Agrega un correo al listado guardado en ``ruta``."""
    from .utils import guardar_json, cargar_json

    ruta = Path(ruta)
    datos = cargar_json(ruta)
    lista = datos.get("destinatarios", []) if isinstance(datos, dict) else []
    if correo in lista:
        return True
    lista.append(correo)
    datos["destinatarios"] = lista
    return guardar_json(datos, ruta)


def eliminar_destinatario(correo: str, ruta: str | Path) -> bool:
    """Elimina un correo del listado de ``ruta``."""
    from .utils import guardar_json, cargar_json

    ruta = Path(ruta)
    datos = cargar_json(ruta)
    lista = datos.get("destinatarios", []) if isinstance(datos, dict) else []
    if correo not in lista:
        return False
    lista.remove(correo)
    datos["destinatarios"] = lista
    return guardar_json(datos, ruta)


def enviar_correo(asunto: str, cuerpo: str, ruta_dest: str | Path, *, host: str = "localhost", port: int = 25) -> bool:
    """Envía un mensaje simple a los destinatarios almacenados."""
    dests = cargar_destinatarios(ruta_dest)
    if not dests:
        return False

    try:
        with smtplib.SMTP(host, port) as server:
            server.set_debuglevel(1)
            server.sendmail("bot@example.com", dests, cuerpo)
        return True
    except Exception as e:  # pragma: no cover - errores dependientes

        logger.error("Error enviando correo: %s", e)
        return False
