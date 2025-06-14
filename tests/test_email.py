# Nombre de archivo: test_email.py
# Ubicación de archivo: tests/test_email.py
# User-provided custom instructions
import sys
import os
import importlib
import tests.telegram_stub  # Registra las clases fake de telegram
from types import ModuleType
from pathlib import Path
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]

# Stub de dotenv
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)
# Variables de entorno minimas definidas en la fixture

# Preparar base de datos en memoria
import sqlalchemy

orig_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")

import sandybot.database as bd

sqlalchemy.create_engine = orig_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)

email_utils = importlib.import_module("sandybot.email_utils")


def test_operaciones_destinatarios():
    cli = bd.Cliente(nombre="Cli")
    with bd.SessionLocal() as s:
        s.add(cli)
        s.commit()
        s.refresh(cli)

    # Inicialmente la lista esta vacia
    assert email_utils.cargar_destinatarios(cli.id) == []

    assert email_utils.agregar_destinatario("a@x.com", cli.id) is True
    assert email_utils.cargar_destinatarios(cli.id) == ["a@x.com"]

    assert email_utils.agregar_destinatario("b@x.com", cli.id, carrier="Telco") is True
    assert email_utils.cargar_destinatarios(cli.id, carrier="Telco") == ["b@x.com"]

    assert set(email_utils.cargar_destinatarios(cli.id)) == {"a@x.com"}

    assert email_utils.eliminar_destinatario("b@x.com", cli.id, carrier="Telco") is True
    assert email_utils.cargar_destinatarios(cli.id, carrier="Telco") == []


def test_enviar_correo(monkeypatch):
    cli = bd.Cliente(nombre="Env")
    with bd.SessionLocal() as s:
        s.add(cli)
        s.commit()
        s.refresh(cli)

    email_utils.agregar_destinatario("c@x.com", cli.id)

    registros = {}

    class DebugSMTP:
        def __init__(self, host, port):
            registros["host"] = host
            registros["port"] = port
            self.sent = []

        def starttls(self):
            registros["tls"] = True

        def login(self, user, pwd):
            registros["login"] = (user, pwd)

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
    monkeypatch.setattr(email_utils.smtplib, "SMTP_SSL", DebugSMTP)

    email_utils.config.SMTP_USER = "bot"
    email_utils.config.SMTP_PASSWORD = "pwd"
    email_utils.config.SMTP_USE_TLS = True

    os.environ.pop("SMTP_DEBUG", None)
    registros.clear()

    ok = email_utils.enviar_correo(
        "Alerta",
        "Prueba",
        cli.id,
        None,
        host="localhost",
        port=1025,
    )

    assert ok is True
    assert registros["host"] == "localhost"
    assert registros["port"] == 1025
    assert registros["tls"] is True
    assert registros["login"] == ("bot", "pwd")
    assert "debug" not in registros

    os.environ["SMTP_DEBUG"] = "1"
    registros.clear()

    ok = email_utils.enviar_correo(
        "Alerta",
        "Prueba",
        cli.id,
        None,
        host="localhost",
        port=1025,
    )

    assert registros["debug"] == 1
    assert registros["sent"][0][1] == ["c@x.com"]
    os.environ.pop("SMTP_DEBUG", None)


def test_enviar_correo_ssl(monkeypatch):
    cli = bd.Cliente(nombre="SSL")
    with bd.SessionLocal() as s:
        s.add(cli)
        s.commit()
        s.refresh(cli)

    email_utils.agregar_destinatario("d@x.com", cli.id)

    registros = {}

    class SSLSMTP:
        def __init__(self, host, port):
            registros["host"] = host
            registros["port"] = port

        def set_debuglevel(self, level):
            registros["debug"] = level

        def starttls(self):
            registros["tls"] = True

        def login(self, user, pwd):
            registros["login"] = (user, pwd)

        def sendmail(self, from_addr, to_addrs, msg):
            registros["sent"] = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(email_utils.smtplib, "SMTP_SSL", SSLSMTP)
    monkeypatch.setattr(email_utils.smtplib, "SMTP", SSLSMTP)

    email_utils.config.SMTP_USER = "u"
    email_utils.config.SMTP_PASSWORD = "p"
    email_utils.config.SMTP_USE_TLS = True

    registros.clear()
    ok = email_utils.enviar_correo(
        "Alerta",
        "SSL",
        cli.id,
        None,
        host="mail",  # host
        port=465,
    )

    assert ok is True
    assert registros["host"] == "mail"
    assert registros["port"] == 465
    assert registros.get("tls") is None
    assert registros.get("login") == ("u", "p")
    assert "debug" not in registros
