# + Nombre de archivo: test_identificador_tarea.py
# + Ubicación de archivo: tests/test_identificador_tarea.py
# User-provided custom instructions
import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from sqlalchemy.orm import sessionmaker
import tempfile

ROOT_DIR = Path(__file__).resolve().parents[1]

from tests.telegram_stub import Message, Update, Document

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

# Stub de extract_msg para leer texto
extract_stub = ModuleType("extract_msg")


class Msg:
    def __init__(self, path):
        self.body = Path(path).read_text()
        self.subject = "asunto"


extract_stub.Message = Msg
sys.modules.setdefault("extract_msg", extract_stub)

# Base de datos en memoria
import sqlalchemy
orig_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")
import sandybot.database as bd
sqlalchemy.create_engine = orig_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)

TEMP_DIR = None


def test_identificador_tarea(tmp_path):
    global TEMP_DIR
    TEMP_DIR = tmp_path
    orig_tmp = tempfile.gettempdir
    tempfile.gettempdir = lambda: str(TEMP_DIR)

    pkg = "sandybot.handlers"
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
        handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
        sys.modules[pkg] = handlers_pkg

    mod_name = f"{pkg}.identificador_tarea"
    spec = importlib.util.spec_from_file_location(
        mod_name,
        ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "identificador_tarea.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    servicio = bd.crear_servicio(nombre="Srv", cliente="Cli")

    import sandybot.email_utils as email_utils
    class GPTStub(email_utils.gpt.__class__):
        async def consultar_gpt(self, mensaje: str, cache: bool = True) -> str:
            return (
                '{"inicio": "2024-01-02T08:00:00", "fin": "2024-01-02T10:00:00", '
                '"tipo": "Mant", "afectacion": "1h", "ids": [' + str(servicio.id) + ']}'
            )
    email_utils.gpt = GPTStub()

    doc = Document(file_name="aviso.msg", content="dummy")
    msg = Message("Cli Telco", document=doc)
    update = Update(message=msg)
    ctx = SimpleNamespace(args=[], user_data={})

    with bd.SessionLocal() as s:
        prev_tareas = s.query(bd.TareaProgramada).count()
        prev_rels = s.query(bd.TareaServicio).count()

    asyncio.run(mod.procesar_identificador_tarea(update, ctx))

    with bd.SessionLocal() as s:
        tareas_list = s.query(bd.TareaProgramada).all()
        tareas = len(tareas_list)
        rels = s.query(bd.TareaServicio).count()

    tempfile.gettempdir = orig_tmp

    assert tareas == prev_tareas + 1
    assert rels == prev_rels + 1
    assert msg.sent == f"tarea_{tareas_list[-1].id}.msg"
