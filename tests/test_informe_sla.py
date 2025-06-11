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

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# ------------------------------------------------------------------ #
#               STUBS Y CONFIGURACIÓN COMPARTIDA                     #
# ------------------------------------------------------------------ #

# ➊ Stub telegram genérico usado por todos los tests
from tests.telegram_stub import Message, Update  # type: ignore

# ➋ Stub dotenv – evita requerir archivo .env
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# ➌ Variables mínimas de entorno
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

# ➍ Stub registrador – captura texto y teclado enviados por el handler
captura: dict[str, object] = {}

registrador_stub = ModuleType("sandybot.registrador")


async def responder_registrando(*args, **kwargs):
    captura["texto"] = args[3]
    captura["reply_markup"] = kwargs.get("reply_markup")


registrador_stub.responder_registrando = responder_registrando
registrador_stub.registrar_conversacion = lambda *a, **k: None
sys.modules["sandybot.registrador"] = registrador_stub


# ------------------------------------------------------------------ #
#               FUNCIÓN DE IMPORTACIÓN DINÁMICA                      #
# ------------------------------------------------------------------ #
def _importar_handler(tmp_path: Path):
    """Genera plantilla temporal y carga dinámicamente el handler."""
    plantilla = tmp_path / "plantilla.docx"
    Document().save(plantilla)

    # Puntero a la plantilla para el handler y para Config
    os.environ["SLA_TEMPLATE_PATH"] = str(plantilla)

    # Stubs sencillos para botones en entornos de pruebas
    class _Btn:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

    class _Markup:
        def __init__(self, keyboard):
            self.inline_keyboard = keyboard

    sys.modules["telegram"].InlineKeyboardButton = _Btn
    sys.modules["telegram"].InlineKeyboardMarkup = _Markup

    # Invalida y recarga configuraciones
    importlib.invalidate_caches()
    if "sandybot.config" in sys.modules:
        importlib.reload(sys.modules["sandybot.config"])

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

    # Fijar plantilla al handler
    mod.RUTA_PLANTILLA = str(plantilla)
    return mod


# ------------------------------------------------------------------ #
#               AYUDANTE PARA DOCUMENTOS EXCEL                       #
# ------------------------------------------------------------------ #
class ExcelDoc:
    """Objeto Telegram-like para adjuntar Excel en los tests."""

    def __init__(self, file_name: str, path: Path):
        self.file_name = file_name
        self._path = path

    async def get_file(self):
        class F:
            async def download_to_drive(_, dest):
                Path(dest).write_bytes(Path(self._path).read_bytes())

        return F()


# ------------------------------------------------------------------ #
#                    FLUJO COMPLETO DE GENERACIÓN                    #
# ------------------------------------------------------------------ #
async def _flujo_completo(tmp_path: Path):
    handler = _importar_handler(tmp_path)
    ctx = SimpleNamespace(user_data={})

    # 1️⃣ Iniciar comando
    await handler.iniciar_informe_sla(Update(message=Message("/sla")), ctx)

    # 2️⃣ Enviar reclamos
    reclamos = pd.DataFrame({"Servicio": ["Srv"], "Fecha": ["2024-01-01"]})
    recl_path = tmp_path / "recl.xlsx"
    reclamos.to_excel(recl_path, index=False)
    await handler.procesar_informe_sla(Update(message=Message(document=ExcelDoc("reclamos.xlsx", recl_path))), ctx)
    assert "Falta el Excel de servicios" in captura["texto"]

    # 3️⃣ Enviar servicios
    captura.clear()
    servicios = pd.DataFrame({"Servicio": ["Srv"]})
    serv_path = tmp_path / "serv.xlsx"
    servicios.to_excel(serv_path, index=False)
    msg_serv = Message(document=ExcelDoc("servicios.xlsx", serv_path))
    await handler.procesar_informe_sla(Update(message=msg_serv), ctx)
    boton = captura["reply_markup"].inline_keyboard[0][0]
    assert boton.callback_data == "sla_procesar"

    # 4️⃣ Procesar informe
    captura.clear()
    cb = SimpleNamespace(data="sla_procesar", message=msg_serv)
    await handler.procesar_informe_sla(Update(callback_query=cb), ctx)

    # El handler envía DOCX y luego lo elimina – verificamos que no quede
    assert msg_serv.sent is not None
    assert not os.path.exists(tmp_path / msg_serv.sent)
    assert ctx.user_data == {}


# ------------------------------------------------------------------ #
#                  CAMBIO DE PLANTILLA DESDE EL BOT                  #
# ------------------------------------------------------------------ #
async def _cambiar_plantilla(tmp_path: Path):
    handler = _importar_handler(tmp_path)
    ctx = SimpleNamespace(user_data={})

    # 1️⃣ Iniciar
    await handler.iniciar_informe_sla(Update(message=Message("/sla")), ctx)

    # 2️⃣ Solicitar cambio
    captura.clear()
    cb = SimpleNamespace(data="sla_cambiar_plantilla", message=Message())
    await handler.procesar_informe_sla(Update(callback_query=cb), ctx)
    assert ctx.user_data.get("cambiar_plantilla") is True

    # 3️⃣ Adjuntar nueva plantilla
    nueva = tmp_path / "nueva.docx"
    Document().save(nueva)
    doc = ExcelDoc("nueva.docx", nueva)
    msg = Message(document=doc)
    msg.document = doc
    await handler.procesar_informe_sla(Update(message=msg), ctx)

    assert "actualizada" in captura["texto"].lower()
    assert Path(handler.RUTA_PLANTILLA).read_bytes() == nueva.read_bytes()
    assert "cambiar_plantilla" not in ctx.user_data


# ------------------------------------------------------------------ #
#        TEST DE GENERACIÓN SIN FECHA Y EXPORTACIÓN A PDF/DOCX       #
# ------------------------------------------------------------------ #
def _generar_basico(handler, tmp_path: Path, exportar_pdf=False):
    reclamos = pd.DataFrame({"Servicio": [1]})
    servicios = pd.DataFrame({"Servicio": [1]})
    r, s = tmp_path / "r.xlsx", tmp_path / "s.xlsx"
    reclamos.to_excel(r, index=False)
    servicios.to_excel(s, index=False)
    ruta = handler._generar_documento_sla(str(r), str(s), exportar_pdf=exportar_pdf)
    assert Path(ruta).exists()
    return ruta


# ------------------------------------------------------------------ #
#                      TEST DE COLUMNAS OPCIONALES                   #
# ------------------------------------------------------------------ #
def _test_columnas_opcionales(handler, tmp_path: Path):
    reclamos = pd.DataFrame({"Servicio": [1], "Fecha": ["2024-01-01"]})
    servicios = pd.DataFrame({"Servicio": [1], "Dirección": ["Calle 1"]})
    r, s = tmp_path / "re.xlsx", tmp_path / "se.xlsx"
    reclamos.to_excel(r, index=False)
    servicios.to_excel(s, index=False)

    ruta = handler._generar_documento_sla(str(r), str(s))
    doc = Document(ruta)
    headers = [c.text for c in doc.tables[0].rows[0].cells]
    assert headers == ["Servicio", "Dirección", "Reclamos"]
    assert doc.tables[0].rows[1].cells[1].text == "Calle 1"


# ------------------------------------------------------------------ #
#                             TESTS                                 #
# ------------------------------------------------------------------ #
def test_flujo_completo(tmp_path):
    asyncio.run(_flujo_completo(tmp_path))


def test_cambiar_plantilla(tmp_path):
    asyncio.run(_cambiar_plantilla(tmp_path))


def test_generar_docx_y_pdf(tmp_path):
    handler = _importar_handler(tmp_path)
    ruta_docx = _generar_basico(handler, tmp_path, exportar_pdf=False)
    assert ruta_docx.endswith(".docx")
    pdf_path = _generar_basico(handler, tmp_path, exportar_pdf=True)
    assert pdf_path.endswith(".pdf") or pdf_path.endswith(".docx")


def test_columnas_opcionales(tmp_path):
    handler = _importar_handler(tmp_path)
    _test_columnas_opcionales(handler, tmp_path)
