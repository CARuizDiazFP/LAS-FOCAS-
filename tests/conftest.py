# Nombre de archivo: conftest.py
# Ubicación de archivo: tests/conftest.py
# User-provided custom instructions
import sys
import os
from types import ModuleType
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]

PKG_PATH = ROOT_DIR / "Sandy bot"
if str(PKG_PATH) not in sys.path:
    sys.path.insert(0, str(PKG_PATH))

import tests.telegram_stub  # Registra telegram y telegram.ext

dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

openai_stub = ModuleType("openai")

class AsyncOpenAI:
    def __init__(self, api_key=None):
        self.chat = type(
            "c", (), {"completions": type("comp", (), {"create": lambda *a, **k: None})()}
        )()

openai_stub.AsyncOpenAI = AsyncOpenAI
sys.modules.setdefault("openai", openai_stub)

REQUIRED_VARS = {
    "TELEGRAM_TOKEN": "x",
    "OPENAI_API_KEY": "x",
    "NOTION_TOKEN": "x",
    "NOTION_DATABASE_ID": "x",
    "DB_USER": "x",
    "DB_PASSWORD": "x",
    "SLACK_WEBHOOK_URL": "x",
    "SUPERVISOR_DB_ID": "x",
}
for key, val in REQUIRED_VARS.items():
    os.environ.setdefault(key, val)


@pytest.fixture(autouse=True)
def entorno_sandy(monkeypatch):
    """Reinicia variables de entorno y ruta para cada prueba."""
    monkeypatch.syspath_prepend(str(PKG_PATH))
    for k, v in REQUIRED_VARS.items():
        monkeypatch.setenv(k, os.getenv(k, v))
    yield
