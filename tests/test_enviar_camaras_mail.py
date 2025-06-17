# Nombre de archivo: test_enviar_camaras_mail.py
# Ubicación de archivo: tests/test_enviar_camaras_mail.py
# User-provided custom instructions
"""Pruebas para el envio de camaras por correo."""

import importlib
import os
import sys
from types import ModuleType
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]

# Stub de smtplib
smtp_stub = ModuleType("smtplib")
reg = {}

class SMTP:
    def __init__(self, host, port):
        reg["host"] = host
        reg["port"] = port
        reg["cls"] = self.__class__.__name__

    def starttls(self):
        reg["tls"] = True

    def login(self, user, pwd):
        reg["login"] = (user, pwd)

    def send_message(self, msg):
        reg["to"] = msg["To"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

class SMTP_SSL(SMTP):
    pass

smtp_stub.SMTP = SMTP
smtp_stub.SMTP_SSL = SMTP_SSL
sys.modules["smtplib"] = smtp_stub


# Base de datos en memoria
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


def _importar():
    pkg = "sandybot.handlers"
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
        handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
        sys.modules[pkg] = handlers_pkg
    mod_name = f"{pkg}.enviar_camaras_mail"
    spec = importlib.util.spec_from_file_location(
        mod_name, ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "enviar_camaras_mail.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_enviar_mail_tls(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "25")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setenv("SMTP_HOST", "mail")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")

    config_mod.Config._instance = None
    importlib.reload(config_mod)

    mod = _importar()
    archivo = tmp_path / "a.txt"
    archivo.write_text("x")
    reg.clear()
    mod._enviar_mail("d@x.com", str(archivo), "a.txt")
    assert reg["cls"] == "SMTP"
    assert reg.get("tls") is True


def test_enviar_mail_ssl(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setenv("SMTP_HOST", "mail")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")

    config_mod.Config._instance = None
    importlib.reload(config_mod)

    mod = _importar()
    archivo = tmp_path / "b.txt"
    archivo.write_text("x")
    reg.clear()
    mod._enviar_mail("d@x.com", str(archivo), "b.txt")
    assert reg["cls"] == "SMTP_SSL"
    assert "tls" not in reg
