# Nombre de archivo: logging_config.py
# Ubicación de archivo: Sandy bot/sandybot/logging_config.py
# User-provided custom instructions
import logging
from logging.handlers import RotatingFileHandler
from .config import config


def setup_logging(level: int = logging.INFO) -> None:
    """Configura logging para consola y archivos con rotación."""
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    # Evitar que bibliotecas como httpx registren tokens o datos sensibles
    logging.getLogger("httpx").setLevel(logging.WARNING)

    consola = logging.StreamHandler()
    consola.setFormatter(formatter)
    root.addHandler(consola)

    archivo = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=1_048_576,
        backupCount=3,
        encoding='utf-8'
    )
    archivo.setFormatter(formatter)
    root.addHandler(archivo)

    errores = RotatingFileHandler(
        config.ERRORES_FILE,
        maxBytes=524_288,
        backupCount=3,
        encoding='utf-8'
    )
    errores.setLevel(logging.ERROR)
    errores.setFormatter(formatter)
    root.addHandler(errores)
