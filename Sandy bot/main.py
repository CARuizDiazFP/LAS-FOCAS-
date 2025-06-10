"""
Punto de entrada principal de la aplicación
"""
import logging
import sys
import os
from pathlib import Path

from sandybot.bot import SandyBot
from sandybot.logging_config import setup_logging

# Asegurar que la ruta de "Sandy bot" figure en PYTHONPATH desde el inicio
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.environ["PYTHONPATH"] = os.pathsep.join(
    filter(None, [os.environ.get("PYTHONPATH"), str(ROOT_DIR)])
)

# Configurar la consola para usar UTF-8 en Windows
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Configurar el sistema de logging en consola y archivos
setup_logging()

def main():
    """Función principal que inicia el bot"""
    try:
        bot = SandyBot()
        bot.run()
    except Exception as e:
        logging.error("Error al iniciar el bot: %s", str(e))
        raise

if __name__ == "__main__":
    main()
