# Nombre de archivo: tests/test_informe_sla.py
# Ubicación: Sandy bot/tests/test_informe_sla.py
# --------------------------------------------------------------------- #
#  Suite de pruebas unificada y libre de conflictos para el handler SLA #
# --------------------------------------------------------------------- #
import sys
import importlib
import asyncio
from pathlib import Path
from types import ModuleType, SimpleNamespace
import os
import pandas as pd
from docx import Document
import tempfile

# ─────────────────────────── PATH DE PROYECTO ─────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# ────────────────────────── STUB TELEGRAM BASE ────────────────────────
from tests.telegram_stub import Message, Update, CallbackQuery  # type: ignore

# ─────────────────── VARIABLES DE ENTORNO MÍNIMAS ─────────────────────
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

for v in [
    "TELEGRAM_TOKEN",
    "OPENAI_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DATABASE_ID",
    "DB_USER",
    "DB_PASSWORD",
    "SLACK_WEBHOOK_URL",
    "SUPERVISOR_DB_ID",
]:
    os.environ.setdefault(v, "x")

# ──────────── STUB REGISTRADOR – CAPTURA RESPUESTAS DEL HANDLER ──────
captura: dict[str, object] = {}

registrador_stub = ModuleType("sandybot.registrador")


async def responder_registrando(*args, **kwargs):
    captura["texto"] = args[3]
    captura["reply_markup"] = kwargs.get("reply_markup")


registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub

# ───────── FUNC. DE IMPORTACIÓN DINÁMICA DEL HANDLER ──────────────────
def _importar_handler(tmp_path: Path):
    plantilla = tmp_path / "plantilla.docx"
    Document().save(plantilla)

    os.environ["SLA_TEMPLATE_PATH"] = str(plantilla)
    hist = tmp_path / "Historios"
    hist.mkdir()
    os.environ["SLA_HISTORIAL_DIR"] = str(hist)

    import importlib as _imp
    import sandybot.config as cfg
    _imp.reload(cfg)

    # Botón / teclado simple (stub)
    class _Btn:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

    class _Mk:
        def __init__(self, keyboard):
            self.inline_keyboard = keyboard

    sys.modules["telegram"].InlineKeyboardButton = _Btn  # type: ignore
    sys.modules["telegram"].InlineKeyboardMarkup = _Mk   # type: ignore
    sys.modules["sandybot.registrador"] = registrador_stub

    # Carga dinámica del handler
    pkg = "sandybot.handlers"
    handlers_pkg = sys.modules.get(pkg) or ModuleType(pkg)
    handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
    sys.modules[pkg] = handlers_pkg

    mod_name = f"{pkg}.informe_sla"
    spec = importlib.util.spec_from_file_location(
        mod_name, ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "informe_sla.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    mod.RUTA_PLANTILLA = str(plantilla)
    return mod

# ──────────────── AYUDANTE PARA DOCUMENTOS EXCEL ──────────────────────
class ExcelDoc:
    def __init__(self, file_name: str, path: Path):
        self.file_name = file_name
        self._path = path

    async def get_file(self):
        class F:
            async def download_to_drive(_, dst):
                Path(dst).write_bytes(Path(self._path).read_bytes())
        return F()

# ───────────────────────── FLUJO COMPLETO SLA ─────────────────────────
async def _flujo_completo(tmp_path: Path):
    handler = _importar_handler(tmp_path)
    ctx = SimpleNamespace(user_data={})

    # /sla
    await handler.iniciar_informe_sla(Update(message=Message("/sla")), ctx)

    # Reclamos
    recl = tmp_path / "recl.xlsx"
    pd.DataFrame({"Servicio": ["Srv"], "Fecha": ["2024-01-01"]}).to_excel(recl, index=False)
    await handler.procesar_informe_sla(Update(message=Message(document=ExcelDoc("recl.xlsx", recl))), ctx)
    assert "Falta el Excel de servicios" in captura["texto"]

    # Servicios
    serv = tmp_path / "serv.xlsx"
    pd.DataFrame({"Servicio": ["Srv"]}).to_excel(serv, index=False)
    msg_serv = Message(document=ExcelDoc("serv.xlsx", serv))
    await handler.procesar_informe_sla(Update(message=msg_serv), ctx)
    assert captura["reply_markup"].inline_keyboard[0][0].callback_data == "sla_procesar"

    # Procesar
    captura.clear()
    cb = SimpleNamespace(data="sla_procesar", message=msg_serv)
    await handler.procesar_informe_sla(Update(callback_query=cb), ctx)

    assert msg_serv.sent and not os.path.exists(tmp_path / msg_serv.sent)

# ───────────── CAMBIO DE PLANTILLA DESDE EL BOT ───────────────────────
async def _cambio_plantilla(tmp_path: Path):
    handler = _importar_handler(tmp_path)
    ctx = SimpleNamespace(user_data={})

    await handler.iniciar_informe_sla(Update(message=Message("/sla")), ctx)

    cb = SimpleNamespace(data="sla_cambiar_plantilla", message=Message())
    await handler.procesar_informe_sla(Update(callback_query=cb), ctx)
    assert ctx.user_data["cambiar_plantilla"]

    nueva = tmp_path / "new.docx"
    Document().save(nueva)
    msg = Message(document=ExcelDoc("new.docx", nueva))
    msg.documents = [msg.document]
    await handler.procesar_informe_sla(Update(message=msg), ctx)

    assert "actualizada" in captura["texto"].lower()
    assert Path(handler.RUTA_PLANTILLA).read_bytes() == nueva.read_bytes()
    hist_dir = Path(os.environ["SLA_HISTORIAL_DIR"])
    assert any(hist_dir.iterdir())

# ───────────── PRUEBA DE COLUMNAS OPCIONALES EN TABLA ─────────────────
def _test_columnas_extra(handler, tmp_path: Path):
    recl = tmp_path / "re.xlsx"
    serv = tmp_path / "se.xlsx"
    pd.DataFrame({"Servicio": [1]}).to_excel(recl, index=False)
    pd.DataFrame({"Servicio": [1], "Dirección": ["Calle 1"]}).to_excel(serv, index=False)
    doc_path = handler._generar_documento_sla(str(recl), str(serv))
    headers = [c.text for c in Document(doc_path).tables[0].rows[0].cells]
    assert headers == ["Servicio", "Dirección", "Reclamos"]

# ───────────────────────── LISTA DE TESTS ─────────────────────────────
def test_flujo_completo(tmp_path):
    asyncio.run(_flujo_completo(tmp_path))

def test_actualizar_plantilla(tmp_path):
    captura.clear()
    asyncio.run(_cambio_plantilla(tmp_path))

def test_columnas_dinamicas(tmp_path):
    handler = _importar_handler(tmp_path)
    _test_columnas_extra(handler, tmp_path)

def test_exportar_pdf(tmp_path):
    """Genera PDF si el entorno lo permite, de lo contrario DOCX."""
    handler = _importar_handler(tmp_path)
    r, s = tmp_path / "r.xlsx", tmp_path / "s.xlsx"
    pd.DataFrame({"Servicio": [1]}).to_excel(r, index=False)
    pd.DataFrame({"Servicio": [1]}).to_excel(s, index=False)
    ruta = handler._generar_documento_sla(str(r), str(s), exportar_pdf=True)
    assert ruta.endswith(".pdf") or ruta.endswith(".docx")
