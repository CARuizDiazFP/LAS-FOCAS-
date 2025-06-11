# Nombre de archivo: tests/test_informe_sla.py
# Ubicación: Sandy bot/tests/test_informe_sla.py
# --------------------------------------------------------------------- #
#  Archivo de pruebas unificado y libre de marcadores de conflicto      #
# --------------------------------------------------------------------- #
import sys
import importlib
import asyncio
from pathlib import Path
from types import ModuleType, SimpleNamespace
import os
import pandas as pd
from docx import Document

# ──────────────────────── CONFIGURACIÓN PATHS ────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# ───────────────────── STUB TELEGRAM COMPARTIDO ──────────────────────
from tests.telegram_stub import Message, Update  # type: ignore

# ─────────────────── VARIABLES DE ENTORNO MÍNIMAS ────────────────────
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

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

# ────────────── STUB REGISTRADOR PARA CAPTURAR RESPUESTAS ────────────
captura: dict[str, object] = {}

registrador_stub = ModuleType("sandybot.registrador")


async def responder_registrando(*args, **kwargs):
    """Guarda el texto y el teclado enviado para las aserciones."""
    captura["texto"] = args[3]
    captura["reply_markup"] = kwargs.get("reply_markup")


registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub

# ───────────────────── IMPORT DINÁMICO DEL HANDLER ───────────────────
def _importar_handler(tmp_path: Path):
    """
    - Genera una plantilla vacía de Word.
    - Sobrescribe RUTA_PLANTILLA en el handler.
    - Recarga dependencias con stubs para evitar Telegram real.
    """
    plantilla = tmp_path / "plantilla.docx"
    Document().save(plantilla)
    os.environ["SLA_TEMPLATE_PATH"] = str(plantilla)

    # Fallbacks simples para botones / teclado si el stub carece de ellos
    class _Btn:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

    class _Markup:
        def __init__(self, keyboard):
            self.inline_keyboard = keyboard

    sys.modules["telegram"].InlineKeyboardButton = _Btn
    sys.modules["telegram"].InlineKeyboardMarkup = _Markup
    sys.modules["sandybot.registrador"] = registrador_stub

    pkg = "sandybot.handlers"
    handlers_pkg = sys.modules.get(pkg) or ModuleType(pkg)
    handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
    sys.modules[pkg] = handlers_pkg

    mod_name = f"{pkg}.informe_sla"
    spec = importlib.util.spec_from_file_location(
        mod_name,
        ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "informe_sla.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    # Fija la plantilla generada para el test
    mod.RUTA_PLANTILLA = str(plantilla)
    return mod


# ────────────────────────── CLASE DOC EXCEL ──────────────────────────
class ExcelDoc:
    """Objeto Telegram‐like para adjuntar Excel en los tests."""

    def __init__(self, file_name: str, path: Path):
        self.file_name = file_name
        self._path = path

    async def get_file(self):
        class F:
            async def download_to_drive(_, dest):
                Path(dest).write_bytes(Path(self._path).read_bytes())

        return F()


# ────────────────────────── FLUJO COMPLETO SLA ───────────────────────
async def _flujo_completo(tmp_path: Path):
    mod = _importar_handler(tmp_path)
    ctx = SimpleNamespace(user_data={})

    # 1️⃣ Iniciar comando /sla
    await mod.iniciar_informe_sla(Update(message=Message("/sla")), ctx)

    # 2️⃣ Enviar Excel de reclamos
    reclamos = pd.DataFrame({"Servicio": ["Srv"], "Fecha": ["2024-01-01"]})
    recl_path = tmp_path / "recl.xlsx"
    reclamos.to_excel(recl_path, index=False)
    await mod.procesar_informe_sla(Update(message=Message(document=ExcelDoc("reclamos.xlsx", recl_path))), ctx)
    assert "Falta el Excel de servicios" in captura["texto"]

    # 3️⃣ Enviar Excel de servicios
    captura.clear()
    servicios = pd.DataFrame({"Servicio": ["Srv"]})
    serv_path = tmp_path / "serv.xlsx"
    servicios.to_excel(serv_path, index=False)
    msg_serv = Message(document=ExcelDoc("servicios.xlsx", serv_path))
    await mod.procesar_informe_sla(Update(message=msg_serv), ctx)
    boton = captura["reply_markup"].inline_keyboard[0][0]
    assert boton.callback_data == "sla_procesar"

    # 4️⃣ Procesar informe con callback
    captura.clear()
    cb = SimpleNamespace(data="sla_procesar", message=msg_serv)
    await mod.procesar_informe_sla(Update(callback_query=cb), ctx)
    # El documento se envía => msg_serv.sent contiene nombre temporal
    assert msg_serv.sent is not None
    assert not os.path.exists(tmp_path / msg_serv.sent)
    assert ctx.user_data == {}


# ───────────────────── CAMBIO DE PLANTILLA SLA ───────────────────────
async def _cambiar_plantilla(tmp_path: Path):
    mod = _importar_handler(tmp_path)
    ctx = SimpleNamespace(user_data={})

    # 1️⃣ Iniciar
    await mod.iniciar_informe_sla(Update(message=Message("/sla")), ctx)

    # 2️⃣ Callback para cambiar plantilla
    captura.clear()
    cb = SimpleNamespace(data="sla_cambiar_plantilla", message=Message())
    await mod.procesar_informe_sla(Update(callback_query=cb), ctx)
    assert ctx.user_data.get("cambiar_plantilla") is True

    # 3️⃣ Adjuntar nueva plantilla
    nueva = tmp_path / "nueva.docx"
    Document().save(nueva)
    doc = ExcelDoc("nueva.docx", nueva)
    msg = Message(document=doc)
    msg.document = doc  # compat
    await mod.procesar_informe_sla(Update(message=msg), ctx)

    assert "actualizada" in captura["texto"].lower()
    assert Path(mod.RUTA_PLANTILLA).read_bytes() == nueva.read_bytes()
    assert "cambiar_plantilla" not in ctx.user_data


# ────────────────────────────── TESTS ────────────────────────────────
def test_flujo_completo(tmp_path):
    asyncio.run(_flujo_completo(tmp_path))