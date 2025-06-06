"""
Configuración centralizada para el bot Sandy
"""
import os
import logging
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """Clase singleton para manejar la configuración global"""
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
        
        # Archivos y rutas
        self.ARCHIVO_CONTADOR = self.DATA_DIR / "contador_diario.json"
        # Registro histórico de interacciones por usuario
        self.ARCHIVO_INTERACCIONES = self.DATA_DIR / "interacciones.json"
        self.LOG_FILE = self.LOG_DIR / "sandy.log"
        self.ERRORES_FILE = self.LOG_DIR / "errores_ingresos.log"

        # Plantilla de informes de repetitividad
        # Permite definir la ruta mediante la variable de entorno "PLANTILLA_PATH"
        # para adaptar la ubicación sin modificar el código fuente.
        self.PLANTILLA_PATH = os.getenv(
            "PLANTILLA_PATH",
            r"C:\\Metrotel\\Sandy\\plantilla_informe.docx"
        )

        # Configuración GPT
        self.GPT_MODEL = "gpt-4"  # o "gpt-3.5-turbo" según necesidad
        self.GPT_TIMEOUT = 30
        self.GPT_MAX_RETRIES = 3
        self.GPT_CACHE_TIMEOUT = 3600  # 1 hora
        
        # Base de datos
        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = os.getenv("DB_PORT", "5432")
        self.DB_NAME = os.getenv("DB_NAME", "sandybot")
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD")
        
        # Validación
        self.validate()
        

        # Configuración de logging gestionada desde `main.py`
        
        self._initialized = True

    def validate(self) -> None:
        """Validar variables de entorno requeridas"""
        required_vars = {
            "TELEGRAM_TOKEN": self.TELEGRAM_TOKEN,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "NOTION_TOKEN": self.NOTION_TOKEN,
            "NOTION_DATABASE_ID": self.NOTION_DATABASE_ID,
            "DB_USER": self.DB_USER,
            "DB_PASSWORD": self.DB_PASSWORD
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

# Instancia global
config = Config()
