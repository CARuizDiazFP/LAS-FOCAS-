# + Nombre de archivo: test_carriers.py
# + Ubicación de archivo: tests/test_carriers.py
# User-provided custom instructions
import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]

from tests.telegram_stub import Message, Update

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
    mod_name = f"{pkg}.carriers"
    sys.modules["sandybot.registrador"] = registrador_stub
    spec = importlib.util.spec_from_file_location(mod_name, ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "carriers.py")
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


def test_operaciones_carriers():
    texto = asyncio.run(_run("agregar_carrier", ["CarrierX"]))
    assert "agregado" in texto

    texto = asyncio.run(_run("listar_carriers", []))
    assert "CarrierX" in texto

    texto = asyncio.run(_run("actualizar_carrier", ["CarrierX", "CarrierY"]))
    assert "actualizado" in texto

    texto = asyncio.run(_run("listar_carriers", []))
    assert "CarrierY" in texto and "CarrierX" not in texto

    texto = asyncio.run(_run("eliminar_carrier", ["CarrierY"]))
    assert "eliminado" in texto

    texto = asyncio.run(_run("listar_carriers", []))
    assert "No hay carriers" in texto
