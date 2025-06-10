import sys
import types
import os
import importlib
from pathlib import Path

# Preparar rutas
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub de dotenv para Config
dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Stub de smtplib para verificar el envío
smtp_stub = types.ModuleType("smtplib")
reg = {"sent": False, "tls": False, "login": None}
class SMTP:
    def __init__(self, host, port):
        reg["host"] = host
        reg["port"] = port
    def starttls(self):
        reg["tls"] = True
    def login(self, user, pwd):
        reg["login"] = (user, pwd)
    def send_message(self, msg):
        reg["sent"] = True
        reg["to"] = msg["To"]
        reg["subject"] = msg["Subject"]
    def quit(self):
        pass
smtp_stub.SMTP = SMTP
smtp_stub.SMTP_SSL = SMTP
sys.modules["smtplib"] = smtp_stub

# Variables de entorno mínimas
os.environ.update({
    "TELEGRAM_TOKEN": "x",
    "OPENAI_API_KEY": "x",
    "NOTION_TOKEN": "x",
    "NOTION_DATABASE_ID": "x",
    "DB_USER": "u",
    "DB_PASSWORD": "p",
    "SLACK_WEBHOOK_URL": "x",
    "SUPERVISOR_DB_ID": "x",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "25",
    "SMTP_USER": "bot@example.com",
    "SMTP_PASSWORD": "pwd",
})

config_mod = importlib.import_module("sandybot.config")
email_utils = importlib.reload(importlib.import_module("sandybot.email_utils"))


def test_enviar_excel_por_correo(tmp_path):
    ruta = tmp_path / "archivo.xlsx"
    ruta.write_text("datos")

    ok = email_utils.enviar_excel_por_correo("dest@example.com", str(ruta))
    assert ok is True
    assert reg["sent"] is True
    assert reg["tls"] is True
    assert reg["login"] == ("bot@example.com", "pwd")
