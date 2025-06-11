# + Nombre de archivo: config.py
# + Ubicación de archivo: Sandy bot/sandybot/config.py
# User-provided custom instructions
"""Configuración centralizada para el bot Sandy.

Este módulo concentra la lectura de todas las variables de entorno
necesarias para ejecutar el bot. A partir de aquí se definen rutas de
trabajo, claves de acceso a APIs y parámetros de conexión.  De esta
forma el resto del código sólo importa :class:`Config` y no debe
preocuparse por dónde provienen esos valores.
"""
import os
import logging
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Clase singleton para manejar la configuración global.

    Al instanciarla se cargan las variables de entorno indispensables
    para el funcionamiento del bot.  Además de las claves de Telegram,
    OpenAI y Notion se añaden ``SLACK_WEBHOOK_URL`` y ``SUPERVISOR_DB_ID``
    que permiten enviar alertas a Slack y registrar acciones en una
    base de Notion destinada al modo supervisor.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Cargar variables de entorno
        load_dotenv()

        # Rutas base
        self.BASE_DIR = Path(__file__).parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.LOG_DIR = self.BASE_DIR / "logs"
        # Carpeta para conservar trackings anteriores
        self.HISTORICO_DIR = self.DATA_DIR / "historico"

        # Crear directorios necesarios
        self.DATA_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)
        self.HISTORICO_DIR.mkdir(exist_ok=True)

        # API Keys
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.NOTION_TOKEN = os.getenv("NOTION_TOKEN")
        self.NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
        # URL del webhook para enviar notificaciones a Slack
        self.SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
        # ID de la base de Notion utilizada en el modo supervisor
        self.SUPERVISOR_DB_ID = os.getenv("SUPERVISOR_DB_ID")

        # Archivos y rutas
        self.ARCHIVO_CONTADOR = self.DATA_DIR / "contador_diario.json"
        # Registro histórico de interacciones por usuario
        self.ARCHIVO_INTERACCIONES = self.DATA_DIR / "interacciones.json"

        # Destinatarios registrados para envío de mensajes

        self.ARCHIVO_DESTINATARIOS = self.DATA_DIR / "destinatarios.json"

        self.LOG_FILE = self.LOG_DIR / "sandy.log"
        self.ERRORES_FILE = self.LOG_DIR / "errores_ingresos.log"
        # Cache de consultas a GPT para reducir costos y latencia
        self.GPT_CACHE_FILE = self.DATA_DIR / "gpt_cache.json"

        # Plantilla de informes de repetitividad
        # La variable "PLANTILLA_PATH" permite ajustar la ruta sin
        # modificar el código fuente.
        self.PLANTILLA_PATH = os.getenv(
            "PLANTILLA_PATH",
            r"C:\\Metrotel\\Sandy\\plantilla_informe.docx"
        )
        # Plantilla para informes de SLA
        # "SLA_TEMPLATE_PATH" permite ajustar la ubicación sin tocar el código
        self.SLA_PLANTILLA_PATH = os.getenv(
            "SLA_TEMPLATE_PATH",
            r"C:\\Metrotel\\Sandy\\Template Informe SLA.docx",
        )
        # Firma opcional en correos
        self.SIGNATURE_PATH = os.getenv("SIGNATURE_PATH")

        # Configuración GPT
        # Permite elegir el modelo vía la variable de entorno "GPT_MODEL".
        # Si no se define, utiliza "gpt-4" por defecto.
        self.GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4")
        self.GPT_TIMEOUT = 30
        self.GPT_MAX_RETRIES = 3
        self.GPT_CACHE_TIMEOUT = 3600  # 1 hora

        # Base de datos

        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = os.getenv("DB_PORT", "5432")
        self.DB_NAME = os.getenv("DB_NAME", "sandybot")
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD")

        # Credenciales de correo electrónico
        smtp_host = os.getenv("SMTP_HOST") or os.getenv(
            "EMAIL_HOST", "smtp.gmail.com"
        )
        smtp_port = os.getenv("SMTP_PORT") or os.getenv("EMAIL_PORT", "465")
        smtp_user = os.getenv("SMTP_USER") or os.getenv("EMAIL_USER")
        smtp_pwd = os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_PASSWORD")

        self.SMTP_HOST = smtp_host
        self.SMTP_PORT = int(smtp_port)
        self.SMTP_USER = smtp_user
        self.SMTP_PASSWORD = smtp_pwd
        self.EMAIL_FROM = os.getenv("EMAIL_FROM")

        # Uso de TLS como booleano
        self.SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

        # Alias de compatibilidad
        self.EMAIL_HOST = self.SMTP_HOST
        self.EMAIL_PORT = self.SMTP_PORT
        self.EMAIL_USER = self.SMTP_USER
        self.EMAIL_PASSWORD = self.SMTP_PASSWORD

        # Validación
        self.validate()

        # Configuración de logging gestionada desde `main.py`

        self._initialized = True

    @property
    def DESTINATARIOS_FILE(self):
        """Alias de compatibilidad para ``ARCHIVO_DESTINATARIOS``."""
        return self.ARCHIVO_DESTINATARIOS

    def validate(self) -> None:
        """Validar variables de entorno requeridas"""
        required_vars = {
            "TELEGRAM_TOKEN": self.TELEGRAM_TOKEN,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "NOTION_TOKEN": self.NOTION_TOKEN,
            "NOTION_DATABASE_ID": self.NOTION_DATABASE_ID,
            "DB_USER": self.DB_USER,
            "DB_PASSWORD": self.DB_PASSWORD,
        }

        missing = [var for var, val in required_vars.items() if not val]
        if missing:
            mensaje = (
                "⚠️ No se encontraron las siguientes variables de entorno "
                f"requeridas: {', '.join(missing)}. "
                "Verificá tu archivo .env o las variables del sistema."
            )
            logging.error(mensaje)
            raise ValueError(mensaje)

        # Verificar variables opcionales de Slack y modo supervisor
        slack_vars = {
            "SLACK_WEBHOOK_URL": self.SLACK_WEBHOOK_URL,
            "SUPERVISOR_DB_ID": self.SUPERVISOR_DB_ID,
        }
        slack_missing = [var for var, val in slack_vars.items() if not val]
        if slack_missing:
            logging.warning(
                "Variables de Slack o supervisor ausentes: %s",
                ", ".join(slack_missing),
            )

        # Advertir si faltan datos de correo
        email_missing = [
            nombre

            for nombre in ["SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM"]

            if not getattr(self, nombre)
        ]
        if email_missing:
            logging.warning(
                "Variables de correo no definidas: %s",
                ", ".join(email_missing),
            )


# Instancia global
config = Config()
