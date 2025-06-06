"""
Manejador de interacciones con GPT con soporte para cache y manejo de errores.
"""
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import openai
from jsonschema import validate, ValidationError
from .config import config
from .utils import cargar_json, guardar_json

logger = logging.getLogger(__name__)

class GPTHandler:
    """
    Clase para manejar interacciones con la API de OpenAI GPT.
    Implementa cache, reintentos, y manejo de rate limits.
    """
    def __init__(self):
        # Cargar la cache desde disco para conservar respuestas entre ejecuciones
        self.cache: Dict[str, Dict[str, str]] = cargar_json(config.GPT_CACHE_FILE)
        # Se crea un cliente asíncrono para la API de OpenAI.
        # De esta forma se aprovecha la nueva interfaz de la
        # biblioteca ``openai`` a partir de la versión 1.x.
        self.client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
    async def consultar_gpt(self, mensaje: str, cache: bool = True) -> str:
        """
        Consulta GPT con manejo de cache y errores

        Args:
            mensaje: El texto a enviar a GPT
            cache: Si True, intenta usar respuesta cacheada

        Returns:
            str: La respuesta de GPT

        Raises:
            Exception: Si no se puede obtener respuesta después de los reintentos
        """
        cache_key = mensaje.strip().lower()
        if cache and cache_key in self.cache:
            entrada = self.cache[cache_key]
            ts = datetime.fromisoformat(entrada["timestamp"])
            if (datetime.now() - ts).seconds < config.GPT_CACHE_TIMEOUT:
                logger.info("Usando respuesta cacheada para: %s", mensaje[:50])
                return entrada["response"]

        # Limpiar respuestas vencidas de la cache
        ahora = datetime.now()
        vencidos = [k for k, v in self.cache.items()
                   if (ahora - datetime.fromisoformat(v["timestamp"])).seconds >= config.GPT_CACHE_TIMEOUT]
        for k in vencidos:
            del self.cache[k]
        if vencidos:
            guardar_json(self.cache, config.GPT_CACHE_FILE)

        for intento in range(config.GPT_MAX_RETRIES):
            try:
                # Utiliza el cliente asíncrono creado en ``__init__`` para
                # solicitar una nueva completitud de chat.
                respuesta = await self.client.chat.completions.create(
                    model=config.GPT_MODEL,
                    messages=[{"role": "user", "content": mensaje}],
                    temperature=0.3,
                    timeout=config.GPT_TIMEOUT
                )
                resultado = respuesta.choices[0].message.content.strip()
                
                if cache:
                    self.cache[cache_key] = {
                        "timestamp": datetime.now().isoformat(),
                        "response": resultado,
                    }
                    guardar_json(self.cache, config.GPT_CACHE_FILE)
                return resultado
                
            except openai.RateLimitError:
                logger.warning("Rate limit alcanzado, reintentando...")
                # Exponential backoff with jitter
                backoff_seconds = (2 ** intento) + (asyncio.get_running_loop().time() % 1)
                await asyncio.sleep(backoff_seconds)
            except openai.APIError as e:
                logger.error("Error de API en consulta GPT: %s", str(e))
                if intento == config.GPT_MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(1)
            except Exception as e:
                logger.error("Error en consulta GPT: %s", str(e))
                if intento == config.GPT_MAX_RETRIES - 1:
                    raise

        raise Exception("No se pudo obtener respuesta de GPT después de varios intentos")

    async def detectar_intencion(self, mensaje: str) -> str:
        """
        Detecta la intención del usuario en el mensaje

        Args:
            mensaje: El texto del usuario

        Returns:
            str: La intención detectada ('acción', 'consulta', o 'neutro')
        """
        prompt = (
            "Clasificá el siguiente mensaje en una sola palabra según la intención del usuario:\n\n"
            "• acción → si está pidiendo que se ejecute algo\n"
            "• consulta → si está pidiendo una explicación\n"
            "• neutro → si es saludo o no se puede clasificar\n\n"
            f"Mensaje: \"{mensaje}\"\n"
            "Respuesta: "
        )
        
        try:
            respuesta = await self.consultar_gpt(prompt)
            salida = respuesta.lower().strip()
            return salida if salida in ["acción", "consulta", "neutro"] else "neutro"
        except Exception as e:
            logger.error("Error al detectar intención: %s", str(e))
            return "neutro"

    async def clasificar_flujo(self, mensaje: str) -> str:
        """Clasifica un mensaje en uno de los flujos disponibles."""
        flujos = [
            "comparar_fo",
            "verificar_ingresos",
            "cargar_tracking",
            "id_carrier",
            "informe_repetitividad",
            "informe_sla",
            "start",
            "otro",
        ]

        opciones = ", ".join(flujos)
        prompt = (
            "Indicá solo el nombre interno del flujo que coincide con el texto.\n"
            f"Opciones: {opciones}.\n"
            f"Texto: '{mensaje}'\n"
            "Respuesta: "
        )

        try:
            respuesta = await self.consultar_gpt(prompt)
            resultado = respuesta.lower().strip()
            return resultado if resultado in flujos else "desconocido"
        except Exception as e:
            logger.error("Error al clasificar flujo: %s", str(e))
            return "desconocido"

    async def generar_pregunta_intencion(self, mensaje: str) -> str:
        """Genera una pregunta de aclaración cuando no se detecta la intención."""
        prompt = (
            "El siguiente mensaje no se entiende del todo: "
            f"'{mensaje}'.\n"
            "Formulá una pregunta breve y amable para pedir más detalles."
        )

        try:
            return await self.consultar_gpt(prompt)
        except Exception as e:
            logger.error("Error al generar pregunta de intención: %s", str(e))
            return "¿Podrías aclarar tu solicitud?"

    async def procesar_json_response(
        self,
        contenido: str,
        schema: Dict[str, Any]
    ) -> Optional[Union[Dict, List]]:
        """
        Procesa y valida una respuesta JSON de GPT usando ``jsonschema``

        Args:
            contenido: La respuesta de GPT en formato JSON
            schema: El esquema esperado para validación

        Returns:
            Optional[Union[Dict, List]]: Datos JSON validados o None si hay error
        """
        try:
            # Limpiar respuesta
            contenido = contenido.strip()
            if contenido.startswith("```"):
                contenido = contenido.split("```")[1]
                if contenido.startswith("json"):
                    contenido = contenido[4:]
                contenido = contenido.strip()
            
            # Parsear JSON
            data = json.loads(contenido)

            # Validar contra el esquema proporcionado
            validate(instance=data, schema=schema)
            return data
        except ValidationError as ve:
            logger.error("JSON no cumple con el esquema: %s", str(ve))
            return None
        except Exception as e:
            logger.error("Error al procesar respuesta JSON de GPT: %s", str(e))
            return None

    async def analizar_incidencias(self, texto: str) -> Optional[List[Dict[str, str]]]:

        """Analiza un texto y extrae una cronología de incidencias."""
        prompt = (
            "Extraé la cronología de incidencias del texto y "
            "devolvé solo un array JSON de objetos con 'fecha' y 'evento'.\n\n"
            f"Texto:\n{texto}"
        )

        esquema = {

            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string"},

                    "evento": {"type": "string"},
                },
                "required": ["fecha", "evento"],

            },
        }

        try:
            respuesta = await self.consultar_gpt(prompt)
            return await self.procesar_json_response(respuesta, esquema)
        except Exception:
            return None

# Instancia global
gpt = GPTHandler()
