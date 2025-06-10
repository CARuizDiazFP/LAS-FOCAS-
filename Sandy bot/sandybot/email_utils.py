"""Funciones utilitarias para el manejo de correos."""

from pathlib import Path
import logging
import smtplib
import os
import re
from datetime import datetime
from email.message import EmailMessage

from .config import config
from .utils import cargar_json, guardar_json

logger = logging.getLogger(__name__)


def cargar_destinatarios(ruta: str | Path) -> list[str]:
    """Devuelve la lista de correos almacenada en ``ruta``."""

    datos = cargar_json(Path(ruta))
    if isinstance(datos, list):
        return datos
    if isinstance(datos, dict):
        return datos.get("emails") or datos.get("destinatarios", [])
    return []


def guardar_destinatarios(destinatarios: list[str], ruta: str | Path) -> bool:
    """Guarda la lista de correos en formato JSON."""

    return guardar_json({"emails": destinatarios}, Path(ruta))


def agregar_destinatario(correo: str, ruta: str | Path) -> bool:
    """Agrega ``correo`` al listado en ``ruta`` si no existe."""

    lista = cargar_destinatarios(ruta)
    if correo not in lista:
        lista.append(correo)
    return guardar_destinatarios(lista, ruta)


def eliminar_destinatario(correo: str, ruta: str | Path) -> bool:
    """Elimina ``correo`` del listado si existe."""

    lista = cargar_destinatarios(ruta)
    if correo not in lista:
        return False
    lista.remove(correo)
    return guardar_destinatarios(lista, ruta)


def enviar_correo(
    asunto: str,
    cuerpo: str,
    ruta_dest: str | Path,
    *,
    host: str | None = None,
    port: int | None = None,
    debug: bool | None = None,
) -> bool:
    """Envía un correo simple a los destinatarios almacenados."""
    correos = cargar_destinatarios(ruta_dest)
    if not correos:
        return False

    host = host or config.SMTP_HOST
    port = port or config.SMTP_PORT

    msg = f"Subject: {asunto}\n\n{cuerpo}"
    try:
        with smtplib.SMTP(host, port) as smtp:
            activar_debug = (
                debug
                if debug is not None
                else os.getenv("SMTP_DEBUG", "0").lower() in {"1", "true", "yes"}
            )
            if activar_debug:
                smtp.set_debuglevel(1)
            smtp.sendmail(config.EMAIL_FROM or config.SMTP_USER, correos, msg)
        return True
    except Exception as e:  # pragma: no cover - depende del entorno
        logger.error("Error enviando correo: %s", e)
        return False


def enviar_excel_por_correo(
    destinatario: str,
    ruta_excel: str,
    *,
    asunto: str = "Reporte SandyBot",
    cuerpo: str = "Adjunto el archivo Excel.",
) -> bool:
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
        use_tls = (
            os.getenv(
                "SMTP_USE_TLS", str(getattr(config, "SMTP_USE_TLS", True))
            ).lower()
            != "false"
        )

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


def _incrementar_contador(clave: str) -> int:
    """Obtiene el próximo número diario para ``clave``."""
    fecha = datetime.now().strftime("%d%m%Y")
    data = cargar_json(config.ARCHIVO_CONTADOR)
    key = f"{clave}_{fecha}"
    numero = data.get(key, 0) + 1
    data[key] = numero
    guardar_json(data, config.ARCHIVO_CONTADOR)
    return numero


def generar_nombre_camaras(id_servicio: int) -> str:
    """Genera el nombre base para un Excel de cámaras."""
    nro = _incrementar_contador("camaras")
    fecha = datetime.now().strftime("%d%m%Y")
    return f"Camaras_{id_servicio}_{fecha}_{nro:02d}"


def generar_nombre_tracking(id_servicio: int) -> str:
    """Genera el nombre base para un archivo de tracking."""
    nro = _incrementar_contador("tracking")
    fecha = datetime.now().strftime("%d%m%Y")
    return f"Tracking_{id_servicio}_{fecha}_{nro:02d}"


def obtener_tracking_reciente(id_servicio: int) -> str | None:
    """Devuelve la ruta del tracking más reciente del histórico."""
    patron = re.compile(rf"tracking_{id_servicio}_(\d{{8}}_\d{{6}})\.txt")
    archivos = []
    for archivo in config.HISTORICO_DIR.glob(f"tracking_{id_servicio}_*.txt"):
        m = patron.match(archivo.name)
        if m:
            archivos.append((m.group(1), archivo))
    if archivos:
        archivos.sort(key=lambda x: x[0], reverse=True)
        return str(archivos[0][1])
    from .database import obtener_servicio

    servicio = obtener_servicio(id_servicio)
    if servicio and servicio.ruta_tracking and os.path.exists(servicio.ruta_tracking):
        return servicio.ruta_tracking
    return None


def enviar_tracking_reciente_por_correo(
    destinatario: str,
    id_servicio: int,
    *,
    asunto: str = "Tracking reciente",
    cuerpo: str = "Adjunto el tracking solicitado.",
) -> bool:
    """Envía por correo el tracking más reciente registrado."""
    ruta = obtener_tracking_reciente(id_servicio)
    if not ruta:
        return False
    nombre = generar_nombre_tracking(id_servicio) + ".txt"
    from .correo import enviar_email

    return enviar_email([destinatario], asunto, cuerpo, ruta, nombre)
