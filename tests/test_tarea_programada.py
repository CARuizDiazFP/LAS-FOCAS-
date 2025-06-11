import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import sessionmaker
import os
import tempfile

# Preparar ruta del paquete
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub de telegram similar al usado en otros tests
telegram_stub = ModuleType("telegram")
class Message:
    def __init__(self, text=""):
        self.text = text
        self.documento = None
    async def reply_document(self, f, filename=None):
        self.documento = filename
    async def reply_text(self, *a, **k):
        pass
class CallbackQuery:
    def __init__(self, message=None):
        self.message = message
class Update:
    def __init__(self, message=None, edited_message=None, callback_query=None):
        self.message = message
        self.edited_message = edited_message
        self.callback_query = callback_query
        self.effective_user = SimpleNamespace(id=1)
class InlineKeyboardButton:
    def __init__(self, *a, **k):
        pass
class InlineKeyboardMarkup:
    def __init__(self, *a, **k):
        pass
telegram_stub.Update = Update
telegram_stub.Message = Message
telegram_stub.CallbackQuery = CallbackQuery
telegram_stub.InlineKeyboardButton = InlineKeyboardButton
telegram_stub.InlineKeyboardMarkup = InlineKeyboardMarkup
telegram_ext_stub = ModuleType("telegram.ext")
class ContextTypes:
    DEFAULT_TYPE = object
telegram_ext_stub.ContextTypes = ContextTypes
telegram_stub.ext = telegram_ext_stub
sys.modules.setdefault("telegram", telegram_stub)
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

# Stubs de openai y jsonschema para importar gpt_handler sin dependencias
openai_stub = ModuleType("openai")
class AsyncOpenAI:
    def __init__(self, api_key=None):
        self.chat = type("c", (), {"completions": type("comp", (), {"create": lambda *a, **k: None})()})()
openai_stub.AsyncOpenAI = AsyncOpenAI
sys.modules.setdefault("openai", openai_stub)

jsonschema_stub = ModuleType("jsonschema")
jsonschema_stub.validate = lambda *a, **k: None
jsonschema_stub.ValidationError = type("ValidationError", (Exception,), {})
sys.modules.setdefault("jsonschema", jsonschema_stub)

# Stub del registrador para evitar llamadas reales a la base
registrador_stub = ModuleType("sandybot.registrador")
async def responder_registrando(*a, **k):
    pass
registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules.setdefault("sandybot.registrador", registrador_stub)

# Stub de dotenv
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables de entorno necesarias
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

# Base de datos en memoria
import sqlalchemy
orig_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")
import sandybot.database as bd
sqlalchemy.create_engine = orig_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)

# Parchar directorio temporal para capturar el .msg
TEMP_DIR = None
def _tmpdir():
    return str(TEMP_DIR)


def test_registrar_tarea_programada(tmp_path):
    global TEMP_DIR
    TEMP_DIR = tmp_path
    orig_tmp = tempfile.gettempdir
    tempfile.gettempdir = _tmpdir

    # Importar handler de forma aislada para evitar dependencias de otros módulos
    pkg = "sandybot.handlers"
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
        handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
        sys.modules[pkg] = handlers_pkg
    mod_name = f"{pkg}.tarea_programada"
    spec = importlib.util.spec_from_file_location(
        mod_name,
        ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "tarea_programada.py",
    )
    tarea_mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = tarea_mod
    spec.loader.exec_module(tarea_mod)

    # Crear servicio previo
    servicio = bd.crear_servicio(nombre="Srv", cliente="Cli")

    msg = Message("/registrar_tarea")
    update = Update(message=msg)
    ctx = SimpleNamespace(args=[
        "Cli",
        "2024-01-02T08:00:00",
        "2024-01-02T10:00:00",
        "Mantenimiento",
        str(servicio.id)
    ])

    with bd.SessionLocal() as s:
        prev_tareas = s.query(bd.TareaProgramada).count()
        prev_rels = s.query(bd.TareaServicio).count()

    asyncio.run(tarea_mod.registrar_tarea_programada(update, ctx))

    with bd.SessionLocal() as s:
        tareas = s.query(bd.TareaProgramada).all()
        rels = s.query(bd.TareaServicio).all()

    tempfile.gettempdir = orig_tmp

    assert len(tareas) == prev_tareas + 1
    assert tareas[-1].tipo_tarea == "Mantenimiento"
    assert len(rels) == prev_rels + 1
    assert rels[-1].tarea_id == tareas[-1].id
    assert rels[-1].servicio_id == servicio.id
    ruta = tmp_path / f"tarea_{tareas[-1].id}.msg"
    assert ruta.exists()
    assert msg.documento == ruta.name
