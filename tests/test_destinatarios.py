# + Nombre de archivo: test_destinatarios.py
# + Ubicación de archivo: tests/test_destinatarios.py
# User-provided custom instructions
import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from sqlalchemy.orm import sessionmaker
import os

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

from tests.telegram_stub import Message, Update

# Stub de dotenv para Config
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

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
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "sandy",
})

import sqlalchemy
orig_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")
import sandybot.database as bd
sqlalchemy.create_engine = orig_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)

# Captura del texto enviado por responder_registrando
captura = {}
registrador_stub = ModuleType("sandybot.registrador")
async def responder_registrando(*a, **k):
    captura["texto"] = a[3]
registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub


def _importar():
    pkg = "sandybot.handlers"
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
        handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
        sys.modules[pkg] = handlers_pkg
    mod_name = f"{pkg}.destinatarios"
    sys.modules["sandybot.registrador"] = registrador_stub
    spec = importlib.util.spec_from_file_location(mod_name, ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "destinatarios.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


async def _run(func, args):
    mod = _importar()
    msg = Message(f"/{func}")
    update = Update(message=msg)
    ctx = SimpleNamespace(args=args)
    captura.clear()
    await getattr(mod, func)(update, ctx)
    return captura.get("texto", "")


def test_listar_por_carrier():
    bd.crear_servicio(nombre="Srv", cliente="CliTest")
    texto = asyncio.run(_run("agregar_destinatario", ["CliTest", "a@x.com"]))
    assert "agregado" in texto
    texto = asyncio.run(_run("agregar_destinatario", ["CliTest", "b@x.com", "Telco"]))
    assert "agregado" in texto

    texto = asyncio.run(_run("listar_destinatarios_por_carrier", ["CliTest"]))
    assert "Generales" in texto and "Telco" in texto
