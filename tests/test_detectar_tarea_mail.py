# + Nombre de archivo: test_detectar_tarea_mail.py
# + Ubicación de archivo: tests/test_detectar_tarea_mail.py
# User-provided custom instructions
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

from tests.telegram_stub import Message, Update  # Registra las clases fake de telegram

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
    import sandybot.email_utils as email_utils
    class GPTStub(email_utils.gpt.__class__):
        async def consultar_gpt(self, mensaje: str, cache: bool = True) -> str:
            return (
                '{"inicio": "2024-01-02T08:00:00", "fin": "2024-01-02T10:00:00", '
                '"tipo": "Mant", "afectacion": "1h", "ids": [' + str(servicio.id) + ']}'
            )

    email_utils.gpt = GPTStub()

    msg = Message("/detectar_tarea Cliente ejemplo correo")
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


def test_cuerpo_sin_carrier(tmp_path):
    """El texto enviado a procesar_correo_a_tarea no incluye el carrier."""

    global TEMP_DIR
    TEMP_DIR = tmp_path
    orig_tmp = tempfile.gettempdir

    tempfile.gettempdir = lambda: str(TEMP_DIR)

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

    import sandybot.email_utils as email_utils

    capturado = {}

    async def stub_procesar(texto, cliente, carrier=None):
        capturado["texto"] = texto
        ruta = tmp_path / "dummy.msg"
        ruta.write_text("x")
        return SimpleNamespace(id=1), SimpleNamespace(nombre=cliente), ruta, "ok"

    email_utils.procesar_correo_a_tarea = stub_procesar
    tarea_mod.procesar_correo_a_tarea = stub_procesar

    msg = Message("/detectar_tarea Cli Telco cuerpo mail")
    update = Update(message=msg)
    ctx = SimpleNamespace(args=["Cli", "Telco"])

    asyncio.run(tarea_mod.detectar_tarea_mail(update, ctx))

    tempfile.gettempdir = orig_tmp

    assert capturado["texto"] == "cuerpo mail"
