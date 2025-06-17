# Nombre de archivo: test_gpt_cache.py
# Ubicación de archivo: tests/test_gpt_cache.py
# User-provided custom instructions
import sys
from types import ModuleType
from pathlib import Path
import importlib
import asyncio

# Preparar rutas para importar el paquete
ROOT_DIR = Path(__file__).resolve().parents[1]

# Stub de telegram con las clases mínimas utilizadas por el código. De esta
# forma evitamos la dependencia real de ``python-telegram-bot`` en las pruebas.
telegram_stub = ModuleType("telegram")

class Update:  # pragma: no cover - comportamiento trivial para pruebas
    pass

class Message:  # pragma: no cover - comportamiento trivial para pruebas
    pass

telegram_stub.Update = Update
telegram_stub.Message = Message
sys.modules.setdefault("telegram", telegram_stub)

# Stub de openai para evitar llamadas reales
openai_stub = ModuleType("openai")
llamadas = {"n": 0}
class CompletionStub:
    async def create(self, *args, **kwargs):
        llamadas["n"] += 1
        class Resp:
            def __init__(self):
                self.choices = [type("msg", (), {"message": type("m", (), {"content": "respuesta"})()})]
        return Resp()
class AsyncOpenAI:
    def __init__(self, api_key=None):
        self.chat = type("c", (), {"completions": CompletionStub()})()
openai_stub.AsyncOpenAI = AsyncOpenAI

# Guardar y reemplazar el módulo original para que otras pruebas
# no se vean afectadas. Si ``openai`` no estaba cargado, se elimina
# al finalizar el test.
openai_original = sys.modules.get("openai")
sys.modules["openai"] = openai_stub

# Stub para jsonschema utilizado por GPTHandler
jsonschema_stub = ModuleType("jsonschema")
class ValidationError(Exception):
    pass
def validate(*args, **kwargs):
    return None
jsonschema_stub.validate = validate
jsonschema_stub.ValidationError = ValidationError
sys.modules.setdefault("jsonschema", jsonschema_stub)


# Variables de entorno mínimas para instanciar Config
import os  # Se usa para modificar variables en otras pruebas
# Las variables mínimas se definen en la fixture global

# Importar módulos de SandyBot
config_mod = importlib.import_module("sandybot.config")


def test_persistencia_cache(tmp_path):
    cache_file = tmp_path / "gpt_cache.json"
    config_mod.config.GPT_CACHE_FILE = cache_file
    # Forzar guardado en disco tras cada consulta
    config_mod.config.GPT_CACHE_SAVE_INTERVAL = 1

    gpt_module = importlib.reload(importlib.import_module("sandybot.gpt_handler"))
    handler = gpt_module.GPTHandler()
    asyncio.run(handler.consultar_gpt("hola"))

    assert llamadas["n"] == 1
    assert cache_file.exists()

    gpt_module = importlib.reload(gpt_module)
    handler2 = gpt_module.GPTHandler()
    asyncio.run(handler2.consultar_gpt("hola"))

    assert llamadas["n"] == 1

    # Restaurar el módulo "openai" para no alterar otras pruebas
    if openai_original is not None:
        sys.modules["openai"] = openai_original
    else:
        sys.modules.pop("openai", None)

