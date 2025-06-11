# + Nombre de archivo: test_informe_sla.py
# + Ubicación de archivo: tests/test_informe_sla.py
# User-provided custom instructions
import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
from sqlalchemy.orm import sessionmaker
import tempfile
import os

import pandas as pd
from docx import Document

# ─────────────────────── ENTORNO & STUBS ────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# --- Telegram stub ----------------------------------------------------------
telegram_stub = ModuleType("telegram")


class InlineKeyboardButton:
    def __init__(self, text: str, callback_data: str | None = None):
        self.text = text
        self.callback_data = callback_data


class InlineKeyboardMarkup:
    def __init__(self, keyboard):
        self.inline_keyboard = keyboard


class DocumentStub:
    def __init__(self, file_name="file.xlsx", content: bytes = b""):
        self.file_name = file_name
        self._content = content

    async def get_file(self):
        class F:
            async def download_to_drive(_, path):
                Path(path).write_bytes(self._content)

        return F()


class Message:
    def __init__(self, *, documents=None, text=""):
        self.documents = documents or []
        self.text = text
        self.sent: str | None = None
        self.markup = None
        self.from_user = SimpleNamespace(id=1)

    async def reply_document(self, f, *, filename=None):
        dest = Path(tempfile.gettempdir()) / filename
        dest.write_bytes(f.read())
        self.sent = filename

    async def reply_text(self, *a, **k):
        # Captura de reply_markup para los asserts
        self.markup = k.get("reply_markup")

    async def edit_text(self, *a, **k):  # pragma: no cover
        pass


class CallbackQuery:
    def __init__(self, data: str = "", message=None):
        self.data = data
        self.message = message

    async def answer(self):  # pragma: no cover
        pass


class Update:
    def __init__(self, *, message=None, callback_query=None, edited_message=None):
        self.message = message
        self.callback_query = callback_query
        self.edited_message = edited_message
        self.effective_user = SimpleNamespace(id=1)


telegram_stub.Update = Update
telegram_stub.Message = Message
telegram_stub.Document = DocumentStub
telegram_stub.CallbackQuery = CallbackQuery
telegram_stub.InlineKeyboardButton = InlineKeyboardButton
telegram_stub.InlineKeyboardMarkup = InlineKeyboardMarkup
sys.modules["telegram"] = telegram_stub

# --- telegram.ext stub ------------------------------------------------------
telegram_ext_stub = ModuleType("telegram.ext")
telegram_ext_stub.ContextTypes = type("C", (), {"DEFAULT_TYPE": object})
sys.modules["telegram.ext"] = telegram_ext_stub

# --- dotenv stub ------------------------------------------------------------
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables mínimas requeridas por Config
for var in [
    "TELEGRAM_TOKEN",
    "OPENAI_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DATABASE_ID",
    "DB_USER",
    "DB_PASSWORD",
    "SLACK_WEBHOOK_URL",
    "SUPERVISOR_DB_ID",
]:
    os.environ.setdefault(var, "x")


# ───────────────────── FUNCIÓN DE IMPORT DINÁMICA ────────────────────
def _importar_handler(tmp_path: Path):
    """
    1. Crea una plantilla vacía de Word y la fija en RUTA_PLANTILLA.
    2. Stub de registrador para capturar reply_markup.
    3. Fuerza SQLite en memoria.
    4. Carga dinámicamente sandybot.handlers.informe_sla y devuelve el módulo.
    """
    template = tmp_path / "template.docx"
    doc = Document()
    doc.add_paragraph("Eventos sucedidos de mayor impacto en SLA:")
    doc.add_paragraph("Conclusión:")
    doc.add_paragraph("Propuesta de mejora:")
    doc.save(template)

    # Stub registrador
    registrador_stub = ModuleType("sandybot.registrador")

    async def responder_registrando(msg, *a, **k):
        if "reply_markup" in k and hasattr(msg, "markup"):
            msg.markup = k["reply_markup"]
        if hasattr(msg, "reply_text"):
            await msg.reply_text(*a, **k)

    registrador_stub.responder_registrando = responder_registrando
    registrador_stub.registrar_conversacion = lambda *a, **k: None
    sys.modules["sandybot.registrador"] = registrador_stub

    # Restablecer stubs de telegram en caso de modificaciones previas
    telegram_stub.InlineKeyboardButton = InlineKeyboardButton
    telegram_stub.InlineKeyboardMarkup = InlineKeyboardMarkup
    sys.modules["telegram"] = telegram_stub

    # Forzar engine SQLite memoria
    import sqlalchemy as sa

    orig_engine = sa.create_engine
    sa.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")

    # (Re)cargar config
    if "sandybot.config" in sys.modules:
        importlib.reload(sys.modules["sandybot.config"])
    else:
        importlib.import_module("sandybot.config")


    # Asegurar paquete handlers
    pkg = "sandybot.handlers"
    handlers_pkg = sys.modules.get(pkg) or ModuleType(pkg)
    handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
    sys.modules[pkg] = handlers_pkg

    # Import dinámico del handler
    mod_name = f"{pkg}.informe_sla"
    spec = importlib.util.spec_from_file_location(
        mod_name, ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "informe_sla.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    import sandybot.database as bd
    # Restaurar engine
    sa.create_engine = orig_engine

    bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
    bd.Base.metadata.create_all(bind=bd.engine)

    # Fijar plantilla
    mod.RUTA_PLANTILLA = str(template)
    return mod


# ──────────────────────────── TEST ───────────────────────────────────
def test_procesar_informe_sla(tmp_path):
    informe = _importar_handler(tmp_path)

    # -------- Datos de prueba --------
    reclamos = pd.DataFrame(
        {
            "ID Servicio": [1, 1, 2],
            "Fecha": pd.to_datetime(["2024-05-01", "2024-05-02", "2024-05-03"]),
        }
    )
    servicios = pd.DataFrame(
        {
            "ID Servicio": [1, 2],
            "Cliente": ["A", "B"],
        }
    )
    r_path = tmp_path / "reclamos.xlsx"
    s_path = tmp_path / "servicios.xlsx"
    reclamos.to_excel(r_path, index=False)
    servicios.to_excel(s_path, index=False)

    doc1 = DocumentStub("reclamos.xlsx", r_path.read_bytes())
    doc2 = DocumentStub("servicios.xlsx", s_path.read_bytes())
    ctx = SimpleNamespace(user_data={})

    # Redirigir tempdir para capturar outputs
    orig_tmp = tempfile.gettempdir
    tempfile.gettempdir = lambda: str(tmp_path)

    try:
        # Paso 1: primer Excel (reclamos)
        msg1 = Message(documents=[doc1])
        asyncio.run(informe.procesar_informe_sla(Update(message=msg1), ctx))
        assert ctx.user_data["archivos"][0] and ctx.user_data["archivos"][1] is None

        # Paso 2: segundo Excel (servicios)
        msg2 = Message(documents=[doc2])
        asyncio.run(informe.procesar_informe_sla(Update(message=msg2), ctx))
        assert all(ctx.user_data["archivos"])
        # Confirmamos botón procesar
        boton = msg2.markup.inline_keyboard[0][0]
        assert boton.callback_data == "sla_procesar"

        # Paso 3: activamos callback
        cb = CallbackQuery("sla_procesar", message=msg2)
        asyncio.run(informe.procesar_informe_sla(Update(callback_query=cb), ctx))
        assert "esperando_eventos" not in ctx.user_data
        assert "esperando_conclusion" not in ctx.user_data
        assert "esperando_propuesta" not in ctx.user_data
        ruta_generada = tmp_path / msg2.sent
        assert ruta_generada.exists()
    finally:
        tempfile.gettempdir = orig_tmp  # Restaurar tempdir

    # -------- Verificaciones de resultado --------
    doc = Document(ruta_generada)

    textos = "\n".join(p.text for p in doc.paragraphs)
    assert "Informe SLA" in textos
    assert "Eventos sucedidos" in textos
    assert "Conclusión:" in textos
    assert "Propuesta de mejora:" in textos

    for p in doc.paragraphs:
        if p.text.startswith("Eventos sucedidos"):
            assert p.text.strip() == "Eventos sucedidos de mayor impacto en SLA:"
        if p.text.startswith("Conclusión:"):
            assert p.text.strip() == "Conclusión:"
        if p.text.startswith("Propuesta de mejora:"):
            assert p.text.strip() == "Propuesta de mejora:"

    tabla = doc.tables[0]
    assert tabla.rows[1].cells[0].text == "1" and tabla.rows[1].cells[1].text == "2"
    assert tabla.rows[2].cells[0].text == "2" and tabla.rows[2].cells[1].text == "1"


def test_generar_sin_fecha(tmp_path):
    """El generador funciona aunque el Excel de reclamos no tenga columna Fecha."""
    informe = _importar_handler(tmp_path)

    reclamos = pd.DataFrame({"Servicio": [1, 2]})
    servicios = pd.DataFrame({"Servicio": [1, 2]})

    r_path = tmp_path / "reclamos.xlsx"
    s_path = tmp_path / "servicios.xlsx"
    reclamos.to_excel(r_path, index=False)
    servicios.to_excel(s_path, index=False)

    ruta = informe._generar_documento_sla(str(r_path), str(s_path))
    assert Path(ruta).exists()
