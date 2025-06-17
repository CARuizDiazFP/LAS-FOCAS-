# Nombre de archivo: test_enviar_camaras_mail.py
# Ubicación de archivo: tests/test_enviar_camaras_mail.py
# User-provided custom instructions
import importlib
import asyncio
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path
import tempfile

from tests.telegram_stub import Message, Update

ROOT_DIR = Path(__file__).resolve().parents[1]

captura = {}
registros = {}


def _importar(tmp_path):
    pkg = "sandybot.handlers"
    if pkg not in sys.modules:
        handlers_pkg = ModuleType(pkg)
        handlers_pkg.__path__ = [str(ROOT_DIR / "Sandy bot" / "sandybot" / "handlers")]
        sys.modules[pkg] = handlers_pkg

    registrador_stub = ModuleType("sandybot.registrador")

    async def responder_registrando(*a, **k):
        captura["texto"] = a[3]

    registrador_stub.responder_registrando = responder_registrando
    registrador_stub.registrar_conversacion = lambda *a, **k: None
    sys.modules["sandybot.registrador"] = registrador_stub

    db_stub = ModuleType("sandybot.database")

    def exportar_camaras_servicio(_id, ruta):
        Path(ruta).write_text("x")
        return True

    db_stub.exportar_camaras_servicio = exportar_camaras_servicio
    sys.modules["sandybot.database"] = db_stub

    email_stub = ModuleType("sandybot.email_utils")

    def enviar_excel_por_correo(dest, ruta_excel, *, asunto="Reporte SandyBot", cuerpo="Adjunto el archivo Excel."):
        registros["dest"] = dest
        registros["ruta"] = ruta_excel
        registros["asunto"] = asunto
        registros["cuerpo"] = cuerpo
        return True

    email_stub.enviar_excel_por_correo = enviar_excel_por_correo
    sys.modules["sandybot.email_utils"] = email_stub

    mod_name = f"{pkg}.enviar_camaras_mail"
    spec = importlib.util.spec_from_file_location(mod_name, ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "enviar_camaras_mail.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


async def _run(mod):
    msg = Message("5 dest@example.com")
    update = Update(message=msg)
    ctx = SimpleNamespace(user_data={})
    await mod.procesar_envio_camaras_mail(update, ctx)


def test_handler_envia_excel(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    mod = _importar(tmp_path)
    captura.clear()
    registros.clear()
    asyncio.run(_run(mod))
    assert registros["dest"] == "dest@example.com"
    assert Path(registros["ruta"]).exists()
    assert registros["asunto"] == "Listado de cámaras"
    assert "cámaras" in registros["cuerpo"].lower()
    assert "enviadas" in captura["texto"]
