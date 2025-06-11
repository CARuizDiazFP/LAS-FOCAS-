# + Nombre de archivo: test_informe_sla.py
# + Ubicacion de archivo: tests/test_informe_sla.py
# User-provided custom instructions
import sys
import importlib
import asyncio
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pandas as pd
from docx import Document

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

from tests.telegram_stub import Message, Update

# Stub de dotenv requerido por config
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables de entorno minimas
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


captura = {}
registrador_stub = ModuleType("sandybot.registrador")
async def responder_registrando(*args, **kwargs):
    captura["texto"] = args[3]
    captura["reply_markup"] = kwargs.get("reply_markup")
registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub


def _importar(tmp_path: Path):
    os.environ["SLA_TEMPLATE_PATH"] = str(tmp_path / "plantilla.docx")
    plantilla = Path(os.environ["SLA_TEMPLATE_PATH"])
    Document().save(plantilla)

    # Clases simples para capturar los callbacks
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
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
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
    mod.RUTA_PLANTILLA = str(plantilla)
    return mod


class ExcelDoc:
    def __init__(self, file_name: str, path: Path):
        self.file_name = file_name
        self._path = path

    async def get_file(self):
        class F:
            async def download_to_drive(_, dest):
                Path(dest).write_bytes(Path(self._path).read_bytes())
        return F()


async def _flujo_completo(tmp_path):
    mod = _importar(tmp_path)
    ctx = SimpleNamespace(user_data={})
    msg = Message("/sla")
    update = Update(message=msg)
    await mod.iniciar_informe_sla(update, ctx)

    reclamos = pd.DataFrame({"Servicio": ["Srv"], "Fecha": ["2024-01-01"]})
    servicios = pd.DataFrame({"Servicio": ["Srv"]})
    recl_path = tmp_path / "recl.xlsx"
    serv_path = tmp_path / "serv.xlsx"
    reclamos.to_excel(recl_path, index=False)
    servicios.to_excel(serv_path, index=False)

    doc_recl = ExcelDoc("reclamos.xlsx", recl_path)
    msg2 = Message(document=doc_recl)
    await mod.procesar_informe_sla(Update(message=msg2), ctx)
    assert "Falta el Excel de servicios" in captura["texto"]

    captura.clear()
    doc_serv = ExcelDoc("servicios.xlsx", serv_path)
    msg3 = Message(document=doc_serv)
    await mod.procesar_informe_sla(Update(message=msg3), ctx)
    boton = captura["reply_markup"].inline_keyboard[0][0]
    assert boton.callback_data == "sla_procesar"

    captura.clear()
    cb = SimpleNamespace(data="sla_procesar", message=msg3)
    await mod.procesar_informe_sla(Update(callback_query=cb), ctx)
    enviado = msg3.documento
    assert enviado and not os.path.exists(enviado)
    assert ctx.user_data == {}


async def _cambiar_plantilla(tmp_path):
    mod = _importar(tmp_path)
    ctx = SimpleNamespace(user_data={})
    msg = Message("/sla")
    await mod.iniciar_informe_sla(Update(message=msg), ctx)

    captura.clear()
    cb = SimpleNamespace(data="sla_cambiar_plantilla", message=msg)
    await mod.procesar_informe_sla(Update(callback_query=cb), ctx)
    assert ctx.user_data.get("cambiar_plantilla") is True

    nueva = tmp_path / "nueva.docx"
    Document().save(nueva)
    doc = ExcelDoc("nueva.docx", nueva)
    msg2 = Message(document=doc)
    await mod.procesar_informe_sla(Update(message=msg2), ctx)
    assert "actualizada" in captura["texto"].lower()
    assert Path(mod.RUTA_PLANTILLA).exists()
    assert "cambiar_plantilla" not in ctx.user_data


def test_flujo_completo(tmp_path):
    asyncio.run(_flujo_completo(tmp_path))


def test_cambiar_plantilla(tmp_path):
    asyncio.run(_cambiar_plantilla(tmp_path))
