"""
Integración con Notion para registro de acciones pendientes
"""
import logging
from datetime import datetime
from notion_client import Client as NotionClient
from ..config import config
from ..utils import cargar_json, guardar_json

logger = logging.getLogger(__name__)
notion = NotionClient(auth=config.NOTION_TOKEN)

async def registrar_accion_pendiente(mensaje_usuario: str, telegram_id: int) -> None:
    """
    Registra una acción pendiente en Notion
    
    Args:
        mensaje_usuario: El mensaje del usuario a registrar
        telegram_id: ID de Telegram del usuario
        
    Raises:
        Exception: Si hay error al registrar en Notion
    """
    try:
        # Cargar y actualizar contador
        fecha_actual = datetime.now().strftime("%d-%m-%Y")
        contador = cargar_json(config.ARCHIVO_CONTADOR)
        
        if fecha_actual not in contador:
            contador[fecha_actual] = 1
        else:
            contador[fecha_actual] += 1
            
        guardar_json(contador, config.ARCHIVO_CONTADOR)

        # Generar ID de solicitud
        id_solicitud = f"{contador[fecha_actual]:03d}"
        nombre_solicitud = f"Solicitud{id_solicitud}{datetime.now().strftime('%d%m%y')}"

        # Crear entrada en Notion
        nueva_entrada = {
            "parent": {"database_id": config.NOTION_DATABASE_ID},
            "properties": {
                "Nombre": {
                    "title": [{"text": {"content": nombre_solicitud}}]
                },
                "Estado": {"select": {"name": "Nuevo"}},
                "Fecha": {"date": {"start": datetime.now().isoformat()}},
                "ID Telegram": {
                    "rich_text": [{"text": {"content": str(telegram_id)}}]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": mensaje_usuario}}]
                    }
                }
            ]
        }

        notion.pages.create(**nueva_entrada)
        logger.info("✅ Acción pendiente registrada como %s", nombre_solicitud)

    except Exception as e:
        logger.error("❌ Error al registrar en Notion: %s", str(e))
        raise
