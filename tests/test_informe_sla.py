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
    def __init__(self, documents=None):
        self.documents = documents or []
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
    template = tmp_path / "template.docx"
    Document().save(template)
    informe.RUTA_PLANTILLA = str(template)
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
    msg = Message(documents=[doc1, doc2])
    upd = Update(message=msg)
    ctx = SimpleNamespace()

    orig_tmp = tempfile.gettempdir
    tempfile.gettempdir = lambda: str(tmp_path)
    try:
        asyncio.run(informe.procesar_informe_sla(upd, ctx))
    finally:
        tempfile.gettempdir = orig_tmp

    ruta = tmp_path / msg.sent
    assert ruta.exists()
    doc = Document(ruta)
    titulo = doc.paragraphs[0].text
    assert "Informe SLA" in titulo
    tabla = doc.tables[0]
    assert tabla.cell(1, 0).text == "1"
    assert tabla.cell(1, 1).text == "2"
    assert tabla.cell(2, 0).text == "2"
    assert tabla.cell(2, 1).text == "1"
