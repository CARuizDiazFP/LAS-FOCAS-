import sys
from types import ModuleType
from pathlib import Path
import importlib
import re
import json

# Agregar ruta de la carpeta "Sandy bot" para importar el paquete
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Crear un stub del módulo telegram para satisfacer las importaciones
telegram_stub = ModuleType("telegram")
class Message:
    def __init__(self, text=""):
        self.text = text
class CallbackQuery:
    def __init__(self, message=None):
        self.message = message
class Update:
    def __init__(self, message=None, edited_message=None, callback_query=None):
        self.message = message
        self.edited_message = edited_message
        self.callback_query = callback_query
telegram_stub.Update = Update
telegram_stub.Message = Message
sys.modules.setdefault("telegram", telegram_stub)

# Importar utils después de preparar el stub
utils = importlib.import_module("sandybot.utils")

def test_normalizar_texto():
    assert utils.normalizar_texto("ÁRBOLES") == "arboles"

def test_normalizar_camara():
    assert utils.normalizar_camara("Cam. Central") == "camara central"

def test_normalizar_camara_abreviaturas():
    esperado = "avenida general san martin"
    assert utils.normalizar_camara("Av. Gral. San Martín") == esperado

def test_guardar_y_cargar_json(tmp_path):
    datos = {"a": 1}
    archivo = tmp_path / "data.json"
    assert utils.guardar_json(datos, archivo) is True
    assert utils.cargar_json(archivo) == datos

def test_cargar_json_inexistente(tmp_path):
    archivo = tmp_path / "noexiste.json"
    assert utils.cargar_json(archivo) == {}

def test_timestamp_log_formato():
    ts = utils.timestamp_log()
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", ts)

def test_obtener_mensaje_callback():
    msg = Message("hola")
    update = Update(callback_query=CallbackQuery(message=msg))
    assert utils.obtener_mensaje(update) is msg
