import sys
import importlib
import asyncio
from types import ModuleType
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub de dotenv necesario para importar config
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables de entorno minimas
import os
for var in [
    "TELEGRAM_TOKEN",
    "OPENAI_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DATABASE_ID",
    "DB_USER",
    "DB_PASSWORD",
    "SLACK_WEBHOOK_URL",
    "SUPERVISOR_DB_ID",
]:
    os.environ.setdefault(var, "x")

# Importar configuración
importlib.import_module("sandybot.config")


def _clasificar(respuesta: str) -> str:
    """Recarga gpt_handler con un stub de openai y devuelve la clasificación."""
    original = sys.modules.get("openai")
    openai_stub = ModuleType("openai")
    class AsyncOpenAI:
        def __init__(self, api_key=None):
            self.chat = type(
                "c", (), {"completions": type("comp", (), {"create": lambda *a, **k: None})()}
            )()

    openai_stub.AsyncOpenAI = AsyncOpenAI
    sys.modules["openai"] = openai_stub
    gpt_module = importlib.reload(importlib.import_module("sandybot.gpt_handler"))

    class Stub(gpt_module.GPTHandler):
        def __init__(self):
            self.cache = {}
            self.client = None

        async def consultar_gpt(self, msg: str, cache: bool = True) -> str:
            return respuesta

    handler = Stub()
    resultado = asyncio.run(handler.clasificar_flujo("texto"))

    if original is not None:
        sys.modules["openai"] = original
    else:
        del sys.modules["openai"]

    return resultado


def test_flujos_nuevos():
    nuevos = [
        "descargar_tracking",
        "descargar_camaras",
        "enviar_camaras_mail",
        "analizar_incidencias",
        "nueva_solicitud",
    ]
    for flujo in nuevos:
        assert _clasificar(flujo) == flujo
