# Nombre de archivo: test_callback_menu.py
# Ubicación de archivo: tests/test_callback_menu.py
# User-provided custom instructions
import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]

from tests.telegram_stub import Message, Update, CallbackQuery

# Stubs para dependencias de otros módulos
notion_mod = ModuleType("notion_client")
class DummyClient:
    def __init__(self, *a, **k):
        pass
notion_mod.Client = DummyClient
sys.modules.setdefault("notion_client", notion_mod)
sys.modules.setdefault("openai", ModuleType("openai"))
js = ModuleType("jsonschema")
js.validate = lambda *a, **k: None
js.ValidationError = Exception
sys.modules.setdefault("jsonschema", js)

# Base de datos en memoria para importar el módulo
import sqlalchemy
orig_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")
import sandybot.database as bd
sqlalchemy.create_engine = orig_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)

# Stubs del registrador
captura = {}
registrador_stub = ModuleType("sandybot.registrador")
async def responder_registrando(*a, **k):
    pass
registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub

# Importar callback con funciones stubs
pkg = "sandybot.handlers"
if pkg not in sys.modules:
    handlers_pkg = ModuleType(pkg)
    handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
    sys.modules[pkg] = handlers_pkg
spec = importlib.util.spec_from_file_location(
    f"{pkg}.callback", ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "callback.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules[f"{pkg}.callback"] = mod
spec.loader.exec_module(mod)

# Reemplazar funciones por stubs para detectar las llamadas
llamadas = {}
async def fake_proc(update, ctx):
    llamadas["proc"] = True
async def fake_list(update, ctx):
    llamadas["list"] = True
sys.modules[f"{pkg}.procesar_correos"] = ModuleType("pc")
sys.modules[f"{pkg}.procesar_correos"].procesar_correos = fake_proc
sys.modules[f"{pkg}.listar_tareas"] = ModuleType("lt")
sys.modules[f"{pkg}.listar_tareas"].mostrar_tareas = fake_list


async def _run(data):
    msg = Message()
    cb = CallbackQuery(message=msg)
    cb.data = data
    update = Update(callback_query=cb)
    ctx = SimpleNamespace(args=[], user_data={})
    await mod.callback_handler(update, ctx)


def test_callback_procesar_correos():
    asyncio.run(_run("procesar_correos"))
    assert llamadas.get("proc") is True


def test_callback_listar_tareas():
    llamadas.clear()
    asyncio.run(_run("listar_tareas"))
    assert llamadas.get("list") is True


def teardown_module(module):
    sys.modules.pop(f"{pkg}.procesar_correos", None)
    sys.modules.pop(f"{pkg}.listar_tareas", None)
