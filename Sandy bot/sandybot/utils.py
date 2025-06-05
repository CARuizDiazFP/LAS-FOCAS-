"""
Funciones de utilidad comunes para el bot
"""

import json
import logging
import unicodedata
from datetime import datetime

from typing import Dict, Any, Optional
from pathlib import Path
from telegram import Update, Message

logger = logging.getLogger(__name__)

def normalizar_texto(texto: str) -> str:
    """
    Normaliza un string para comparaciones (elimina acentos, mayúsculas, etc)
    
    Args:
        texto: Texto a normalizar
        
    Returns:
        str: Texto normalizado
    """
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()

def cargar_json(ruta: Path) -> Dict:
    """
    Carga un archivo JSON de forma segura
    
    Args:
        ruta: Path al archivo JSON
        
    Returns:
        Dict: Datos del JSON o diccionario vacío si hay error
    """
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar JSON de {ruta}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error al cargar {ruta}: {e}")
        return {}

def guardar_json(datos: Dict, ruta: Path) -> bool:
    """
    Guarda datos en un archivo JSON de forma segura
    
    Args:
        datos: Diccionario a guardar
        ruta: Path donde guardar el archivo
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error al guardar {ruta}: {e}")
        return False

def timestamp_log() -> str:
    """
    Genera un timestamp para logs
    
    Returns:
        str: Timestamp en formato YYYY-MM-DD HH:MM:SS
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


from telegram import Update, Message
from typing import Optional

def obtener_mensaje(update: Update) -> Optional[Message]:
    """Obtiene el objeto Message desde un Update.

    Esta función permite unificar la extracción del mensaje ya sea
    proveniente de actualizaciones directas o de callbacks.

    Args:
        update: Update recibido por el bot.

    Returns:
        Message o ``None`` si no existe.
    """
    if update.message:
        return update.message
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message
    return None
