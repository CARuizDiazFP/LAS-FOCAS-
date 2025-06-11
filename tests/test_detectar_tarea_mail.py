import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import sessionmaker
import os
import tempfile

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stubs de telegram
telegram_stub = ModuleType("telegram")

class Message:
    def __init__(self, text="", document=None):
        self.text = text
        self.document = document
        self.sent = None

    async def reply_document(self, f, filename=None):
        self.sent = filename

    async def reply_text(self, *a, **k):
        pass


class Document:
    def __init__(self, file_name="mail.txt", content=""):
        self.file_name = file_name
        self._content = content

    async def get_file(self):
        class F:
            async def download_to_drive(_, path):
                Path(path).write_text(self._content)

        return F()


class Update:
    def __init__(self, message=None, edited_message=None, callback_query=None):
        self.message = message
        self.edited_message = edited_message
        self.callback_query = callback_query
        self.effective_user = SimpleNamespace(id=1)


telegram_stub.Update = Update
telegram_stub.Message = Message
telegram_stub.CallbackQuery = SimpleNamespace
telegram_stub.Document = Document
sys.modules.setdefault("telegram", telegram_stub)

telegram_ext_stub = ModuleType("telegram.ext")
class ContextTypes:
    DEFAULT_TYPE = object

telegram_ext_stub.ContextTypes = ContextTypes
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

# Stubs de openai y jsonschema
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

TEMP_DIR = None


def test_detectar_tarea_mail(tmp_path, monkeypatch):
    global TEMP_DIR
    TEMP_DIR = tmp_path
    orig_tmp = tempfile.gettempdir

    def _tmpdir():
        return str(TEMP_DIR)

    tempfile.gettempdir = _tmpdir

    pkg = "sandybot.handlers"
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
        handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
        sys.modules[pkg] = handlers_pkg

    mod_name = f"{pkg}.detectar_tarea_mail"
    spec = importlib.util.spec_from_file_location(
        mod_name,
        ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "detectar_tarea_mail.py",
    )
    tarea_mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = tarea_mod
    spec.loader.exec_module(tarea_mod)

    # Crear servicio previo
    servicio = bd.crear_servicio(nombre="Srv", cliente="Cli")

    # Contar registros antes de ejecutar
    with bd.SessionLocal() as s:
        prev_tareas = s.query(bd.TareaProgramada).count()
        prev_rels = s.query(bd.TareaServicio).count()

    # Stub GPT para devolver JSON
    class GPTStub(tarea_mod.gpt.__class__):
        async def consultar_gpt(self, mensaje: str, cache: bool = True) -> str:
            return (
                '{"inicio": "2024-01-02T08:00:00", "fin": "2024-01-02T10:00:00", '
                '"tipo": "Mant", "afectacion": "1h", "ids": [' + str(servicio.id) + ']}'
            )

    tarea_mod.gpt = GPTStub()

    msg = Message("/detectar_tarea Cliente ejemplo")
    update = Update(message=msg)
    ctx = SimpleNamespace(args=["Cliente", "ejemplo"])

    asyncio.run(tarea_mod.detectar_tarea_mail(update, ctx))

    with bd.SessionLocal() as s:
        tareas = s.query(bd.TareaProgramada).all()
        rels = s.query(bd.TareaServicio).all()

    tempfile.gettempdir = orig_tmp

    assert len(tareas) == prev_tareas + 1
    assert len(rels) == prev_rels + 1
    tarea = tareas[-1]
    rel = rels[-1]
    assert rel.tarea_id == tarea.id
    assert rel.servicio_id == servicio.id
    ruta = tmp_path / f"tarea_{tarea.id}.msg"
    assert ruta.exists()
    assert msg.sent == ruta.name
