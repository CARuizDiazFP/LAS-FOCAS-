# + Nombre de archivo: test_userstate.py
# + Ubicación de archivo: tests/test_userstate.py
# User-provided custom instructions
import sys
import os
import importlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

# Preparar entorno de importacion
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Stub del modulo dotenv requerido por config
dotenv_stub = ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Stub del modulo telegram con clases basicas
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
class InlineKeyboardButton:
    def __init__(self, *args, **kwargs):
        pass
class InlineKeyboardMarkup:
    def __init__(self, *args, **kwargs):
        pass
telegram_stub.Update = Update
telegram_stub.Message = Message
telegram_stub.CallbackQuery = CallbackQuery
telegram_stub.InlineKeyboardButton = InlineKeyboardButton
telegram_stub.InlineKeyboardMarkup = InlineKeyboardMarkup
telegram_ext_stub = ModuleType("telegram.ext")
class ContextTypes:
    DEFAULT_TYPE = object
telegram_ext_stub.ContextTypes = ContextTypes
telegram_stub.ext = telegram_ext_stub
sys.modules.setdefault("telegram", telegram_stub)
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

# Stub de sqlalchemy para evitar dependencias reales
sqlalchemy_stub = ModuleType("sqlalchemy")
class Column:
    def __init__(self, *args, **kwargs):
        pass
class Integer: pass
class String: pass
class DateTime: pass
def create_engine(*args, **kwargs):
    return None
def text(value):
    return value
def inspect(engine):
    class Insp:
        def get_columns(self, table):
            return []
    return Insp()
sqlalchemy_stub.create_engine = create_engine
sqlalchemy_stub.Column = Column
sqlalchemy_stub.Integer = Integer
sqlalchemy_stub.String = String
sqlalchemy_stub.DateTime = DateTime
sqlalchemy_stub.text = text
sqlalchemy_stub.inspect = inspect
sqlalchemy_orm = ModuleType("sqlalchemy.orm")
def declarative_base():
    class Base:
        class metadata:
            @staticmethod
            def create_all(bind=None):
                pass
    return Base
def sessionmaker(bind=None):
    def maker(*args, **kwargs):
        return None
    return maker
sqlalchemy_orm.declarative_base = declarative_base
sqlalchemy_orm.sessionmaker = sessionmaker
sqlalchemy_stub.orm = sqlalchemy_orm
sys.modules.setdefault("sqlalchemy", sqlalchemy_stub)
sys.modules.setdefault("sqlalchemy.orm", sqlalchemy_orm)

# Stubs para las capas de base de datos y registro
database_stub = ModuleType("sandybot.database")
class Conversacion:
    pass
def SessionLocal():
    class Session:
        def add(self, *args, **kwargs):
            pass
        def commit(self):
            pass
        def close(self):
            pass
    return Session()
database_stub.SessionLocal = SessionLocal
database_stub.Conversacion = Conversacion
sys.modules.setdefault("sandybot.database", database_stub)

registrador_stub = ModuleType("sandybot.registrador")
def responder_registrando(*args, **kwargs):
    pass
registrador_stub.responder_registrando = responder_registrando
sys.modules.setdefault("sandybot.registrador", registrador_stub)

# Variables requeridas por Config
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

# Importar config despues de establecer las variables
config_mod = importlib.import_module("sandybot.config")


def cargar_estado(tmp_path):
    """Carga ``estado.py`` evitando importar el resto de handlers."""
    config_mod.config.ARCHIVO_INTERACCIONES = tmp_path / "interacciones.json"
    pkg_name = "sandybot.handlers"
    if pkg_name not in sys.modules:
        handlers_pkg = ModuleType(pkg_name)
        handlers_pkg.__path__ = []
        sys.modules[pkg_name] = handlers_pkg
    mod_name = f"{pkg_name}.estado"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name,
        ROOT_DIR / "Sandy bot" / "sandybot" / "handlers" / "estado.py",
    )
    estado = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = estado
    spec.loader.exec_module(estado)
    return estado


def test_set_get_mode(tmp_path):
    estado = cargar_estado(tmp_path)
    uid = 1
    estado.UserState.set_mode(uid, "test")
    assert estado.UserState.get_mode(uid) == "test"


def test_increment_interaction(tmp_path):
    estado = cargar_estado(tmp_path)
    uid = 2
    first = estado.UserState.increment_interaction(uid)
    assert first == 1
    assert estado.UserState.get_interaction(uid) == 1
    with open(config_mod.config.ARCHIVO_INTERACCIONES, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data[str(uid)] == 1


def test_cleanup_old_sessions(tmp_path):
    estado = cargar_estado(tmp_path)
    uid_old = 3
    uid_new = 4
    estado.UserState.set_mode(uid_old, "old")
    estado.UserState.set_mode(uid_new, "new")
    estado.UserState.get_user(uid_old).last_interaction = datetime.now() - timedelta(hours=48)
    estado.UserState.get_user(uid_new).last_interaction = datetime.now()
    estado.UserState.cleanup_old_sessions(max_age_hours=24)
    assert uid_old not in estado.UserState._users
    assert uid_new in estado.UserState._users
