import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
import tempfile

import pandas as pd
from docx import Document

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub telegram similar to otras pruebas
telegram_stub = ModuleType("telegram")
class DocumentStub:
    def __init__(self, file_name="file.xlsx", content=b""):
        self.file_name = file_name
        self._content = content
    async def get_file(self):
        class F:
            async def download_to_drive(_, path):
                Path(path).write_bytes(self._content)
        return F()
class Message:
    def __init__(self, documents=None, text=""):
        self.documents = documents or []
        self.text = text
        self.sent = None
        self.from_user = SimpleNamespace(id=1)
    async def reply_document(self, f, filename=None):
        dest = Path(tempfile.gettempdir()) / filename
        dest.write_bytes(f.read())
        self.sent = filename
    async def reply_text(self, *a, **k):
        pass
class Update:
    def __init__(self, message=None):
        self.message = message
        self.effective_user = SimpleNamespace(id=1)
telegram_stub.Update = Update
telegram_stub.Message = Message
telegram_stub.Document = DocumentStub
sys.modules.setdefault("telegram", telegram_stub)

telegram_ext_stub = ModuleType("telegram.ext")
telegram_ext_stub.ContextTypes = type("C", (), {"DEFAULT_TYPE": object})
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

# Stub dotenv
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables mínimas
import os
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

importlib.import_module("sandybot.config")

pkg = "sandybot.handlers"
handlers_pkg = ModuleType(pkg)
handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
sys.modules.setdefault(pkg, handlers_pkg)

mod_name = f"{pkg}.informe_sla"
spec = importlib.util.spec_from_file_location(
    mod_name,
    ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "informe_sla.py",
)
informe = importlib.util.module_from_spec(spec)
sys.modules[mod_name] = informe
spec.loader.exec_module(informe)


def test_procesar_informe_sla(tmp_path):
    reclamos = pd.DataFrame({
        "ID Servicio": [1, 1, 2],
        "Fecha": pd.to_datetime(["2024-05-01", "2024-05-02", "2024-05-03"]),
    })
    servicios = pd.DataFrame({
        "ID Servicio": [1, 2],
        "Cliente": ["A", "B"],
    })
    r_path = tmp_path / "reclamos.xlsx"
    s_path = tmp_path / "servicios.xlsx"
    reclamos.to_excel(r_path, index=False)
    servicios.to_excel(s_path, index=False)

    doc1 = DocumentStub("reclamos.xlsx", r_path.read_bytes())
    doc2 = DocumentStub("servicios.xlsx", s_path.read_bytes())
    ctx = SimpleNamespace(user_data={})

    orig_tmp = tempfile.gettempdir
    tempfile.gettempdir = lambda: str(tmp_path)
    try:
        # Paso 1: envío de archivos
        msg1 = Message(documents=[doc1, doc2])
        upd1 = Update(message=msg1)
        asyncio.run(informe.procesar_informe_sla(upd1, ctx))
        assert ctx.user_data.get("esperando_eventos")
        assert msg1.sent is None

        # Paso 2: eventos
        msg2 = Message(text="ev")
        asyncio.run(informe.procesar_informe_sla(Update(message=msg2), ctx))
        assert ctx.user_data.get("esperando_conclusion")

        # Paso 3: conclusion
        msg3 = Message(text="conc")
        asyncio.run(informe.procesar_informe_sla(Update(message=msg3), ctx))
        assert ctx.user_data.get("esperando_propuesta")

        # Paso 4: propuesta y generación
        msg4 = Message(text="prop")
        asyncio.run(informe.procesar_informe_sla(Update(message=msg4), ctx))
    finally:
        tempfile.gettempdir = orig_tmp

    ruta = tmp_path / msg4.sent
    assert ruta.exists()
    doc = Document(ruta)
    textos = "\n".join(p.text for p in doc.paragraphs)
    tabla = doc.tables[0]
    assert "Informe SLA" in textos
    assert tabla.rows[1].cells[0].text == "1"
    assert tabla.rows[2].cells[0].text == "2"
    assert "ev" in textos
    assert "conc" in textos
    assert "prop" in textos
