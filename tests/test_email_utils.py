import sys
import types
import os
import importlib
from pathlib import Path
from datetime import datetime

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


smtp_stub.SMTP = SMTP
smtp_stub.SMTP_SSL = SMTP
sys.modules["smtplib"] = smtp_stub

# Variables de entorno mínimas
os.environ.update(
    {
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
        "SMTP_USE_TLS": "true",
    }
)

from sandybot import config as config_mod
config_mod.Config._instance = None
importlib.reload(config_mod)
config_mod = importlib.import_module("sandybot.config")
email_utils = importlib.reload(importlib.import_module("sandybot.email_utils"))


def test_enviar_excel_por_correo(tmp_path):
    ruta = tmp_path / "archivo.xlsx"
    ruta.write_text("datos")

    ok = email_utils.enviar_excel_por_correo("dest@example.com", str(ruta))
    assert ok is True
    assert reg["host"] == "smtp.example.com"
    assert reg["port"] == 25
    assert reg["sent"] is True
    assert reg["tls"] is True
    assert reg["login"] == (
        email_utils.config.SMTP_USER,
        email_utils.config.SMTP_PASSWORD,
    )


def test_enviar_excel_por_correo_compatibilidad(tmp_path, monkeypatch):
    """El envío funciona si solo se definen variables EMAIL_*"""
    reg.clear()
    # Eliminar variables SMTP para forzar el uso de EMAIL_*
    for var in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"]:
        os.environ.pop(var, None)
    os.environ.update(
        {
            "EMAIL_HOST": "smtp.legacy.com",
            "EMAIL_PORT": "26",
            "EMAIL_USER": "old@example.com",
            "EMAIL_PASSWORD": "oldpwd",
        }
    )
    import importlib

    config_mod.Config._instance = None
    importlib.reload(config_mod)
    importlib.reload(email_utils)

    ruta = tmp_path / "archivo.xlsx"
    ruta.write_text("datos")
    ok = email_utils.enviar_excel_por_correo("dest@example.com", str(ruta))
    assert ok is True
    assert reg["host"] == "smtp.legacy.com"
    assert reg["port"] == 26
    assert reg["login"] == ("old@example.com", "oldpwd")


def test_generar_nombres(tmp_path):
    email_utils.config.ARCHIVO_CONTADOR = tmp_path / "cont.json"
    nombre1 = email_utils.generar_nombre_camaras(5)
    nombre2 = email_utils.generar_nombre_camaras(5)
    hoy = datetime.now().strftime("%d%m%Y")
    assert nombre1 == f"Camaras_5_{hoy}_01"
    assert nombre2 == f"Camaras_5_{hoy}_02"


def test_enviar_tracking_reciente_por_correo(tmp_path):
    email_utils.config.HISTORICO_DIR = tmp_path
    (tmp_path / "tracking_7_20240101_000000.txt").write_text("a")
    reciente = tmp_path / "tracking_7_20240102_000000.txt"
    reciente.write_text("b")
    email_utils.config.ARCHIVO_CONTADOR = tmp_path / "cont.json"
    reg.clear()
    ok = email_utils.enviar_tracking_reciente_por_correo("d@x.com", 7)
    assert ok is True
    assert reg["sent"] is True
