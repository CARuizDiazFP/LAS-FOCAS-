import sys
import os
import importlib
from types import ModuleType
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub de telegram requerido por utils
telegram_stub = ModuleType("telegram")
class Message:
    def __init__(self, text=""):
        self.text = text
class CallbackQuery:
    def __init__(self, message=None):
        self.message = message
class Update:
    def __init__(self, message=None, edited_message=None, callback_query=None):
        self.message = message
        self.edited_message = edited_message
        self.callback_query = callback_query
telegram_stub.Update = Update
telegram_stub.Message = Message
sys.modules.setdefault("telegram", telegram_stub)

# Stub de dotenv
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables de entorno minimas
for var in [
    "TELEGRAM_TOKEN",
    "OPENAI_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DATABASE_ID",
    "DB_USER",
    "DB_PASSWORD",
    "SLACK_WEBHOOK_URL",
    "SUPERVISOR_DB_ID",
    "EMAIL_FROM",
]:
    os.environ.setdefault(var, "x")

email_utils = importlib.import_module("sandybot.email_utils")


def test_operaciones_destinatarios(tmp_path):
    json_path = tmp_path / "dest.json"

    # Inicialmente la lista esta vacia
    assert email_utils.cargar_destinatarios(json_path) == []

    # Agregar correos
    assert email_utils.agregar_destinatario("a@x.com", json_path) is True
    assert email_utils.cargar_destinatarios(json_path) == ["a@x.com"]

    assert email_utils.agregar_destinatario("b@x.com", json_path) is True
    assert set(email_utils.cargar_destinatarios(json_path)) == {"a@x.com", "b@x.com"}

    # Eliminar un correo
    assert email_utils.eliminar_destinatario("a@x.com", json_path) is True
    assert email_utils.cargar_destinatarios(json_path) == ["b@x.com"]


def test_enviar_correo(monkeypatch, tmp_path):
    json_path = tmp_path / "dest.json"
    email_utils.agregar_destinatario("c@x.com", json_path)

    registros = {}

    class DebugSMTP:
        def __init__(self, host, port):
            registros["host"] = host
            registros["port"] = port
            self.sent = []

        def set_debuglevel(self, level):
            registros["debug"] = level

        def sendmail(self, from_addr, to_addrs, msg):
            self.sent.append((from_addr, to_addrs, msg))
            registros.setdefault("sent", []).extend(self.sent)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(email_utils.smtplib, "SMTP", DebugSMTP)

    ok = email_utils.enviar_correo("Alerta", "Prueba", json_path, host="localhost", port=1025)

    assert ok is True
    assert registros["host"] == "localhost"
    assert registros["port"] == 1025
    assert registros["debug"] == 1
    assert registros["sent"][0][1] == ["c@x.com"]
