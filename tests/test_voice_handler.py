import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub telegram con soporte de mensajes de voz
telegram_stub = ModuleType("telegram")
telegram_stub = sys.modules.setdefault("telegram", telegram_stub)
class VoiceFile:
    async def download_to_drive(self, path):
        Path(path).write_bytes(b"")
class Voice:
    async def get_file(self):
        return VoiceFile()
class User:
    def __init__(self, id=1):
        self.id = id
class Message:
    def __init__(self, text=None, voice=None):
        self.text = text
        self.voice = voice
        self.from_user = User()
    async def reply_text(self, *a, **k):
        pass
class Update:
    def __init__(self, message=None):
        self.message = message
        self.effective_user = message.from_user if message else None
telegram_stub.Update = Update
telegram_stub.Message = Message
telegram_stub.InlineKeyboardButton = object
telegram_stub.InlineKeyboardMarkup = object
telegram_ext_stub = ModuleType("telegram.ext")
telegram_ext_stub.ContextTypes = type("ContextTypes", (), {"DEFAULT_TYPE": object})
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

# Stub dotenv
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables de entorno mínimas
import os
for var in [
    "TELEGRAM_TOKEN",
    "OPENAI_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DATABASE_ID",
    "SLACK_WEBHOOK_URL",
    "SUPERVISOR_DB_ID",
    "DB_USER",
    "DB_PASSWORD",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
]:
    os.environ.setdefault(var, "25" if var == "SMTP_PORT" else "x")

# Stub de openai compatible con GPTHandler y voice_handler.
# Guardamos el módulo original para restaurarlo tras cada prueba.
openai_original = sys.modules.get("openai")
openai_stub = ModuleType("openai")

class CompletionStub:
    async def create(self, *args, **kwargs):
        class Resp:
            def __init__(self):
                self.choices = [type("msg", (), {"message": type("m", (), {"content": "ok"})()})]

        return Resp()


class AsyncOpenAI:
    def __init__(self, api_key=None):
        self.chat = type("c", (), {"completions": CompletionStub()})()

        async def create_audio(*a, **k):
            class R:
                text = "texto voz"
            return R()

        self.audio = type("a", (), {"transcriptions": type("t", (), {"create": create_audio})()})()


class RateLimitError(Exception):
    pass


class APIError(Exception):
    pass


openai_stub.AsyncOpenAI = AsyncOpenAI
openai_stub.RateLimitError = RateLimitError
openai_stub.APIError = APIError
sys.modules["openai"] = openai_stub

# Restaurar el stub de ``openai`` al finalizar cada prueba para
# evitar que otros tests hereden este reemplazo.
import pytest

@pytest.fixture(autouse=True)
def _restaurar_openai():
    sys.modules["openai"] = openai_stub
    yield
    if openai_original is not None:
        sys.modules["openai"] = openai_original
    else:
        sys.modules.pop("openai", None)

# Crear paquete handlers con un stub de message_handler
handlers_pkg = ModuleType("sandybot.handlers")
captura = {}
message_stub = ModuleType("sandybot.handlers.message")
async def message_handler(update, context):
    captura["texto"] = context.user_data.pop("voice_text", None) or update.message.text
    captura["original"] = getattr(update.message, "text", None)
message_stub.message_handler = message_handler
sys.modules["sandybot.handlers.message"] = message_stub

# Stub registrador para evitar dependencias
registrador_stub = ModuleType("sandybot.registrador")
async def responder_registrando(*a, **k):
    pass
registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub

handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
sys.modules.setdefault("sandybot.handlers", handlers_pkg)

# Con el paquete stub listo importamos ``voice`` para las pruebas.
config_mod = importlib.import_module("sandybot.config")
voice_module = importlib.import_module("sandybot.handlers.voice")
voice_module.message_handler = message_handler

# Restaurar el módulo ``openai`` para no interferir con la colección
if openai_original is not None:
    sys.modules["openai"] = openai_original
else:
    sys.modules.pop("openai", None)


def test_voice_no_modifica_update():
    upd = Update(message=Message(voice=Voice()))
    ctx = SimpleNamespace(user_data={})
    asyncio.run(voice_module.voice_handler(upd, ctx))
    assert captura["texto"] == "texto voz"
    assert captura["original"] is None
    assert upd.message.text is None
    assert ctx.user_data == {}
