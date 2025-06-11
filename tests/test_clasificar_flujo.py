import sys
import importlib
import asyncio
from types import ModuleType
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub de dotenv necesario para importar config
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables de entorno minimas
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

# Importar configuración
importlib.import_module("sandybot.config")


def _clasificar(respuesta: str) -> str:
    """Recarga gpt_handler con un stub de openai y devuelve la clasificación."""
    original = sys.modules.get("openai")
    openai_stub = ModuleType("openai")
    class AsyncOpenAI:
        def __init__(self, api_key=None):
            self.chat = type(
                "c", (), {"completions": type("comp", (), {"create": lambda *a, **k: None})()}
            )()

    openai_stub.AsyncOpenAI = AsyncOpenAI
    sys.modules["openai"] = openai_stub
    gpt_module = importlib.reload(importlib.import_module("sandybot.gpt_handler"))

    class Stub(gpt_module.GPTHandler):
        def __init__(self):
            self.cache = {}
            self.client = None

        async def consultar_gpt(self, msg: str, cache: bool = True) -> str:
            return respuesta

    handler = Stub()
    resultado = asyncio.run(handler.clasificar_flujo("texto"))

    if original is not None:
        sys.modules["openai"] = original
    else:
        del sys.modules["openai"]

    return resultado


def test_flujos_nuevos():
    nuevos = [
        "descargar_tracking",
        "descargar_camaras",
        "enviar_camaras_mail",
        "analizar_incidencias",
        "nueva_solicitud",
        "informe_sla",
    ]
    for flujo in nuevos:
        assert _clasificar(flujo) == flujo


def _detectar(texto: str) -> str:
    pkg_name = "sandybot.handlers"
    handlers_pkg = ModuleType(pkg_name)
    handlers_pkg.__path__ = []

    stubs = {
        pkg_name: handlers_pkg,
        "telegram": ModuleType("telegram"),
        "telegram.ext": ModuleType("telegram.ext"),
        "sandybot.gpt_handler": ModuleType("sandybot.gpt_handler"),
        "sandybot.database": ModuleType("sandybot.database"),
        "sandybot.registrador": ModuleType("sandybot.registrador"),
        "sandybot.handlers.estado": ModuleType("sandybot.handlers.estado"),
        "sandybot.handlers.notion": ModuleType("sandybot.handlers.notion"),
        "sandybot.handlers.ingresos": ModuleType("sandybot.handlers.ingresos"),
        "sandybot.handlers.comparador": ModuleType("sandybot.handlers.comparador"),
        "sandybot.handlers.cargar_tracking": ModuleType("sandybot.handlers.cargar_tracking"),
        "sandybot.handlers.repetitividad": ModuleType("sandybot.handlers.repetitividad"),
        "sandybot.handlers.id_carrier": ModuleType("sandybot.handlers.id_carrier"),
        "sandybot.handlers.informe_sla": ModuleType("sandybot.handlers.informe_sla"),
    }

    stubs["telegram"].Update = object
    stubs["telegram"].InlineKeyboardButton = object
    stubs["telegram"].InlineKeyboardMarkup = object
    stubs["telegram"].Message = object
    stubs["telegram"].CallbackQuery = object

    stubs["sandybot.database"].obtener_servicio = lambda *a, **k: None
    stubs["sandybot.database"].crear_servicio = lambda *a, **k: None
    stubs["sandybot.registrador"].responder_registrando = lambda *a, **k: None
    stubs["sandybot.handlers.estado"].UserState = type("U", (), {})
    stubs["sandybot.handlers.notion"].registrar_accion_pendiente = lambda *a, **k: None
    stubs["sandybot.handlers.ingresos"].verificar_camara = lambda *a, **k: None
    async def _a(*a, **k):
        return None
    stubs["sandybot.handlers.ingresos"].iniciar_verificacion_ingresos = _a
    stubs["sandybot.handlers.comparador"].iniciar_comparador = _a
    stubs["sandybot.handlers.cargar_tracking"].guardar_tracking_servicio = lambda *a, **k: None
    stubs["sandybot.handlers.cargar_tracking"].iniciar_carga_tracking = _a
    stubs["sandybot.handlers.repetitividad"].iniciar_repetitividad = _a
    stubs["sandybot.handlers.id_carrier"].iniciar_identificador_carrier = _a
    stubs["sandybot.handlers.informe_sla"].iniciar_informe_sla = _a

    class CT:
        DEFAULT_TYPE = object()
    stubs["telegram.ext"].ContextTypes = CT
    stubs["sandybot.gpt_handler"].gpt = object()

    backups = {}
    for name, mod in stubs.items():
        backups[name] = sys.modules.get(name)
        sys.modules[name] = mod

    mod_name = f"{pkg_name}.message"
    spec = importlib.util.spec_from_file_location(
        mod_name,
        ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "message.py",
    )
    message = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = message
    spec.loader.exec_module(message)
    resultado = message._detectar_accion_natural(texto)

    # Restaurar módulos originales
    for name, mod in backups.items():
        if mod is None:
            del sys.modules[name]
        else:
            sys.modules[name] = mod
    del sys.modules[mod_name]

    return resultado


def test_variantes_diccionario():
    detectar = _detectar

    ejemplos = {
        "cmp fo": "comparar_fo",
        "desc trk": "descargar_tracking",
        "env cams mail": "enviar_camaras_mail",
        "verfiar ingrsos": "verificar_ingresos",
        "inf sla": "informe_sla",
    }

    for texto, esperado in ejemplos.items():
        assert detectar(texto) == esperado

