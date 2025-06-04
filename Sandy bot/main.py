"""
Punto de entrada principal de la aplicación
"""
import logging
import sys
import os
from sandybot.bot import SandyBot

# Configurar la consola para usar UTF-8 en Windows
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Configurar el logger raíz con nivel de registro, formato y stream (UTF-8)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Usar el sys.stdout reconfigurado
)

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
