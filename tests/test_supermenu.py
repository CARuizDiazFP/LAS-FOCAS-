# Nombre de archivo: test_supermenu.py
# Ubicación de archivo: tests/test_supermenu.py
# User-provided custom instructions
import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]

from tests.telegram_stub import Message, Update
# Variables mínimas configuradas en la fixture global

import sqlalchemy
orig_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")
import sandybot.database as bd
sqlalchemy.create_engine = orig_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)

captura = {}
registrador_stub = ModuleType("sandybot.registrador")
async def responder_registrando(*a, **k):
    captura["texto"] = a[3]
    captura["markup"] = k.get("reply_markup")
registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub


def _importar():
    pkg = "sandybot.handlers"
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
        handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
        sys.modules[pkg] = handlers_pkg
    mod_name = f"{pkg}.supermenu"
    sys.modules["sandybot.registrador"] = registrador_stub
    spec = importlib.util.spec_from_file_location(mod_name, ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "supermenu.py")
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
    return captura


def test_supermenu_teclado():
    res = asyncio.run(_run("supermenu", ["Bio123"]))
    assert res["markup"].keyboard[0] == [
        "/CDB_Servicios",
        "/CDB_Reclamos",
        "/CDB_Camaras",
        "/Depurar_Duplicados",
    ]


def test_listar_descendente():
    s1 = bd.crear_servicio(nombre="S1", cliente="A")
    s2 = bd.crear_servicio(nombre="S2", cliente="B")
    bd.crear_reclamo(s1.id, "R1")
    bd.crear_reclamo(s2.id, "R2")
    bd.crear_camara("C1", s1.id)
    bd.crear_camara("C2", s2.id)
    texto_serv = asyncio.run(_run("listar_servicios", []))["texto"]
    assert texto_serv.splitlines()[1].startswith("1. ") and str(s2.id) in texto_serv.splitlines()[1]
    texto_rec = asyncio.run(_run("listar_reclamos", []))["texto"]
    assert texto_rec.splitlines()[1].startswith("1. ") and "R2" in texto_rec.splitlines()[1]
    texto_cam = asyncio.run(_run("listar_camaras", []))["texto"]
    assert texto_cam.splitlines()[1].startswith("1. ") and "C2" in texto_cam.splitlines()[1]


def test_depurar_duplicados():
    bd.Base.metadata.drop_all(bind=bd.engine)
    bd.Base.metadata.create_all(bind=bd.engine)
    s1 = bd.crear_servicio(nombre="Dup", cliente="X")
    bd.crear_servicio(nombre="Dup", cliente="X")
    bd.crear_reclamo(s1.id, "R10")
    bd.crear_reclamo(bd.crear_servicio(nombre="Otro", cliente="X").id, "R10")
    texto = asyncio.run(_run("depurar_duplicados", []))["texto"]
    assert "Servicios eliminados: 1" in texto
    assert "Reclamos eliminados: 1" in texto
