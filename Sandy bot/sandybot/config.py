# Nombre de archivo: config.py
# Ubicación de archivo: Sandy bot/sandybot/config.py
# User-provided custom instructions: Siemple escribe en español y explica en detalles para que sirven las lineas modificadas, agregadas o quitadas.
"""Configuración centralizada para el bot Sandy.

Este módulo concentra la lectura de todas las variables de entorno
necesarias para ejecutar el bot.  El resto del código sólo importa
:class:`Config` y no debe preocuparse por cómo se obtienen estos valores.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv


class Config:  # pylint: disable=too-many-instance-attributes
    """Singleton con toda la configuración global del bot."""

    _instance: "Config | None" = None

    # ───────────────────── INSTANCIACIÓN ÚNICA ──────────────────────
    def __new__(cls, *args, **kwargs):  # noqa: D401
        if cls._instance is None:
            cls._instance = super().__new__(cls)  # type: ignore[misc]
            cls._instance._initialized = False
        return cls._instance

    # ───────────────────────── CONSTRUCTOR ──────────────────────────
    def __init__(self) -> None:
        if self._initialized:  # evita re-inicializar singleton
            return

        # 1) Cargar variables de entorno desde .env (si existe)
        load_dotenv()

        # 2) Directorios base del proyecto
        self.BASE_DIR = Path(__file__).parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.LOG_DIR = self.BASE_DIR / "logs"
        self.HISTORICO_DIR = self.DATA_DIR / "historico"


        # Rutas historial/plantillas SLA
        self.SLA_HISTORIAL_DIR = Path(
            os.getenv("SLA_HISTORIAL_DIR", self.BASE_DIR / "templates" / "Historicos")
        )

        # Crear carpetas necesarias (idempotente)
        for carpeta in (
            self.DATA_DIR,
            self.LOG_DIR,
            self.HISTORICO_DIR,
            self.SLA_HISTORIAL_DIR,
        ):
            carpeta.mkdir(parents=True, exist_ok=True)

        # 3) API Keys y TOKENS
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.NOTION_TOKEN = os.getenv("NOTION_TOKEN")
        self.NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
        self.SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
        self.SUPERVISOR_DB_ID = os.getenv("SUPERVISOR_DB_ID")

        # 4) Archivos comunes
        self.ARCHIVO_CONTADOR = self.DATA_DIR / "contador_diario.json"
        self.ARCHIVO_INTERACCIONES = self.DATA_DIR / "interacciones.json"
        self.ARCHIVO_DESTINATARIOS = self.DATA_DIR / "destinatarios.json"
        self.LOG_FILE = self.LOG_DIR / "sandy.log"
        self.ERRORES_FILE = self.LOG_DIR / "errores_ingresos.log"
        self.GPT_CACHE_FILE = self.DATA_DIR / "gpt_cache.json"

        # 5) Plantillas
        self.PLANTILLA_PATH = os.getenv(
            "PLANTILLA_PATH",
            str(self.BASE_DIR / "templates" / "plantilla_informe.docx"),
        )
        self.SLA_PLANTILLA_PATH = os.getenv(
            "SLA_TEMPLATE_PATH",
            str(self.BASE_DIR / "templates" / "Template Informe SLA.docx"),
        )
        Path(self.SLA_PLANTILLA_PATH).parent.mkdir(parents=True, exist_ok=True)

        # 6) Firma de correos opcional
        self.SIGNATURE_PATH = os.getenv("SIGNATURE_PATH")

        # 7) GPT
        self.GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4")
        self.GPT_TIMEOUT = 30
        self.GPT_MAX_RETRIES = 3
        self.GPT_CACHE_TIMEOUT = 3600  # 1 hora

        # 8) Conexión BD
        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = os.getenv("DB_PORT", "5432")
        self.DB_NAME = os.getenv("DB_NAME", "sandybot")
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD")

        # 9) SMTP / Email
        self.SMTP_HOST = os.getenv("SMTP_HOST", os.getenv("EMAIL_HOST", "smtp.gmail.com"))
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", os.getenv("EMAIL_PORT", "465")))
        self.SMTP_USER = os.getenv("SMTP_USER", os.getenv("EMAIL_USER"))
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", os.getenv("EMAIL_PASSWORD"))
        self.EMAIL_FROM = os.getenv("EMAIL_FROM")
        self.SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

        # Aliases legacy
        self.EMAIL_HOST = self.SMTP_HOST
        self.EMAIL_PORT = self.SMTP_PORT
        self.EMAIL_USER = self.SMTP_USER
        self.EMAIL_PASSWORD = self.SMTP_PASSWORD

        # Validación final
        self._validate_env()

        self._initialized = True

    # ---------------------------------------------------------------- #
    @property
    def DESTINATARIOS_FILE(self):  # noqa: D401
        """Alias de compatibilidad posterior."""
        return self.ARCHIVO_DESTINATARIOS

    # ---------------------------------------------------------------- #
    def _validate_env(self) -> None:
        """Comprueba variables obligatorias y lanza errores / warnings."""
        obligatorias = {
            "TELEGRAM_TOKEN": self.TELEGRAM_TOKEN,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "NOTION_TOKEN": self.NOTION_TOKEN,
            "NOTION_DATABASE_ID": self.NOTION_DATABASE_ID,
            "DB_USER": self.DB_USER,
            "DB_PASSWORD": self.DB_PASSWORD,
        }
        faltantes = [v for v, val in obligatorias.items() if not val]
        if faltantes:
            raise ValueError(
                "Variables de entorno requeridas faltantes: " + ", ".join(faltantes)
            )

        opcionales = {
            "SLACK_WEBHOOK_URL": self.SLACK_WEBHOOK_URL,
            "SUPERVISOR_DB_ID": self.SUPERVISOR_DB_ID,
        }
        warn = [v for v, val in opcionales.items() if not val]
        if warn:
            logging.warning("Variables opcionales ausentes: %s", ", ".join(warn))

        email_faltantes = [
            n for n in ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM") if not getattr(self, n)
        ]
        if email_faltantes:
            logging.warning("Variables de correo no definidas: %s", ", ".join(email_faltantes))


# Instancia global
config = Config()
