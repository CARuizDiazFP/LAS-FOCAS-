import sys
import importlib
import asyncio
from types import ModuleType, SimpleNamespace
from pathlib import Path
import tempfile
import os

import pandas as pd
from docx import Document

# ─────────────────────── ENTORNO & STUBS ────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Telegram stub (mínimo para pruebas)
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
        self.sent: str | None = None
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

# telegram.ext stub
telegram_ext_stub = ModuleType("telegram.ext")
telegram_ext_stub.ContextTypes = type("C", (), {"DEFAULT_TYPE": object})
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

# dotenv stub
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

# Carga Config
importlib.import_module("sandybot.config")

# Cargar dinámicamente el módulo handler (informe_sla.py)
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


# ──────────────────────────── TEST ───────────────────────────────────
def test_procesar_informe_sla(tmp_path):
    # 1) Plantilla vacía
    template = tmp_path / "template.docx"
    Document().save(template)
    informe.RUTA_PLANTILLA = str(template)

    # 2) Datos de prueba
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

    # 3) Stub documentos Telegram
    doc1 = DocumentStub("reclamos.xlsx", r_path.read_bytes())
    doc2 = DocumentStub("servicios.xlsx", s_path.read_bytes())
    ctx = SimpleNamespace(user_data={})

    # Redirigir carpeta temporal para capturar archivos generados
    orig_tmp = tempfile.gettempdir
    tempfile.gettempdir = lambda: str(tmp_path)

    try:
        # Paso 1: envíamos ambos Excel
        msg1 = Message(documents=[doc1, doc2])
        upd1 = Update(message=msg1)
        asyncio.run(informe.procesar_informe_sla(upd1, ctx))
        assert ctx.user_data.get("esperando_eventos")
        assert msg1.sent is None  # Aún no se envió documento

        # Paso 2: eventos
        msg2 = Message(text="Evento crítico")
        asyncio.run(informe.procesar_informe_sla(Update(message=msg2), ctx))
        assert ctx.user_data.get("esperando_conclusion")

        # Paso 3: conclusión
        msg3 = Message(text="Conclusión X")
        asyncio.run(informe.procesar_informe_sla(Update(message=msg3), ctx))
        assert ctx.user_data.get("esperando_propuesta")

        # Paso 4: propuesta y generación final
        msg4 = Message(text="Propuesta Y")
        asyncio.run(informe.procesar_informe_sla(Update(message=msg4), ctx))
    finally:
        tempfile.gettempdir = orig_tmp  # Restaurar

    # 4) Verifica documento generado
    ruta_generada = tmp_path / msg4.sent
    assert ruta_generada.exists()
    doc = Document(ruta_generada)

    # Validaciones básicas
    textos = "\n".join(p.text for p in doc.paragraphs)
    assert "Informe SLA" in textos
    assert "Evento crítico" in textos
    assert "Conclusión X" in textos
    assert "Propuesta Y" in textos

    # Tabla servicio-reclamos
    tabla = doc.tables[0]
    assert tabla.rows[1].cells[0].text == "1"          # Servicio 1
    assert tabla.rows[1].cells[1].text == "2"          # 2 reclamos
    assert tabla.rows[2].cells[0].text == "2"          # Servicio 2
    assert tabla.rows[2].cells[1].text == "1"          # 1 reclamo
