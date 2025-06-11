import sys
import types
import os
import importlib
from pathlib import Path
from sqlalchemy.orm import sessionmaker
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

# Base de datos en memoria para las pruebas
import sqlalchemy
orig = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig("sqlite:///:memory:")
import sandybot.database as bd
sqlalchemy.create_engine = orig
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)

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


def test_enviar_correo_a_cliente(monkeypatch):
    cli = bd.Cliente(nombre="Mail", destinatarios=["m@x.com"])
    with bd.SessionLocal() as s:
        s.add(cli)
        s.commit()
        s.refresh(cli)

    class DebugSMTP:
        def __init__(self, host, port):
            reg["host"] = host
            reg["port"] = port

        def starttls(self):
            reg["tls"] = True

        def login(self, u, p):
            reg["login"] = (u, p)

        def sendmail(self, f, to, msg):
            reg["sent"] = to

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(email_utils.smtplib, "SMTP", DebugSMTP)
    monkeypatch.setattr(email_utils.smtplib, "SMTP_SSL", DebugSMTP)

    reg.clear()
    ok = email_utils.enviar_correo("Aviso", "Hola", cli.id, host="h", port=25)
    assert ok is True
    assert reg["sent"] == ["m@x.com"]


def test_generar_archivo_msg(tmp_path):
    cli = bd.Cliente(nombre="AcmeX", destinatarios=["x@y.com"])
    with bd.SessionLocal() as s:
        s.add(cli)
        s.commit()
        s.refresh(cli)

    srv = bd.crear_servicio(nombre="S1", cliente="AcmeX", cliente_id=cli.id)
    tarea = bd.crear_tarea_programada(
        datetime(2024, 1, 2, 8),
        datetime(2024, 1, 2, 10),
        "Mantenimiento",
        [srv.id],
    )

    ruta = tmp_path / "aviso.msg"
    email_utils.generar_archivo_msg(tarea, cli, [srv], str(ruta))
    assert ruta.exists()
    contenido = ruta.read_text(encoding="utf-8")
    assert "Mantenimiento" in contenido
