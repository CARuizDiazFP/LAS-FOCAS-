# Nombre de archivo: test_proxima_tarea.py
# Ubicación de archivo: tests/test_proxima_tarea.py
# User-provided custom instructions
import sys
import importlib
from types import ModuleType
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]

# Registrar stubs básicos de telegram
from tests.telegram_stub import Message, Update

import sqlalchemy
orig_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_engine("sqlite:///:memory:")
import sandybot.database as bd
sqlalchemy.create_engine = orig_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)


def teardown_module(module):
    bd.Base.metadata.drop_all(bind=bd.engine)


def test_obtener_proxima_tarea():
    srv = bd.crear_servicio(nombre="Srv", cliente="A")
    ahora = datetime.utcnow()
    bd.crear_tarea_programada(ahora - timedelta(hours=2), ahora - timedelta(hours=1), "Pasada", [srv.id])
    t2 = bd.crear_tarea_programada(ahora + timedelta(hours=1), ahora + timedelta(hours=2), "Siguiente", [srv.id])
    bd.crear_tarea_programada(ahora + timedelta(hours=3), ahora + timedelta(hours=4), "Lejana", [srv.id])
    proxima = bd.obtener_proxima_tarea()
    assert proxima.id == t2.id

