"""Utilidades sencillas para el envio de correos."""

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import List

from .utils import cargar_json, guardar_json


def cargar_destinatarios(ruta: Path) -> List[str]:
    """Devuelve la lista de emails almacenados en ``ruta``."""
    datos = cargar_json(ruta)
    if isinstance(datos, list):
        return datos
    return []


def guardar_destinatarios(destinatarios: List[str], ruta: Path) -> bool:
    """Guarda la lista de destinatarios en ``ruta``."""
    return guardar_json(destinatarios, ruta)


def agregar_destinatario(correo: str, ruta: Path) -> bool:
    """Agrega un correo a la lista si no esta presente."""
    dest = cargar_destinatarios(ruta)
    if correo not in dest:
        dest.append(correo)
    return guardar_destinatarios(dest, ruta)


def eliminar_destinatario(correo: str, ruta: Path) -> bool:
    """Elimina un correo de la lista si existe."""
    dest = cargar_destinatarios(ruta)
    if correo in dest:
        dest.remove(correo)
    return guardar_destinatarios(dest, ruta)


def enviar_correo(asunto: str, cuerpo: str, ruta: Path, host: str = "localhost", port: int = 25) -> bool:
    """Envía un correo simple a todos los destinatarios registrados."""
    destinatarios = cargar_destinatarios(ruta)
    if not destinatarios:
        return False

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = "sandy@example.com"
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(host, port) as smtp:
        smtp.set_debuglevel(1)
        smtp.sendmail(mensaje["From"], destinatarios, mensaje.as_string())
    return True

