import os
import sys
import importlib
from pathlib import Path
from datetime import datetime
import pytest
import openpyxl

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Agregar ruta del paquete
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

# Crear stub del módulo telegram para las utilidades
telegram_stub = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("telegram", None))
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

# Stub de dotenv requerido por config
dotenv_stub = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("dotenv", None))
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)

# Variables de entorno necesarias para Config
required_vars = {
    "TELEGRAM_TOKEN": "x",
    "OPENAI_API_KEY": "x",
    "NOTION_TOKEN": "x",
    "NOTION_DATABASE_ID": "x",
    "DB_USER": "user",
    "DB_PASSWORD": "pass",
    "SLACK_WEBHOOK_URL": "x",
    "SUPERVISOR_DB_ID": "x",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "sandy",
}
os.environ.update(required_vars)

# Forzar que ``sandybot.database`` utilice SQLite en memoria
import sqlalchemy

orig_create_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_create_engine("sqlite:///:memory:")

bd = importlib.import_module("sandybot.database")

sqlalchemy.create_engine = orig_create_engine
bd.SessionLocal = sessionmaker(bind=bd.engine, expire_on_commit=False)
bd.Base.metadata.create_all(bind=bd.engine)


def test_buscar_servicios_por_camara():
    bd.crear_servicio(nombre="S1", cliente="A", camaras=["Cámara Central"])
    bd.crear_servicio(nombre="S2", cliente="B", camaras=["Nodo Secundario"])
    bd.crear_servicio(nombre="S3", cliente="C", camaras=["Avenida General San Martin"])

    res1 = bd.buscar_servicios_por_camara("camara central")
    assert {s.nombre for s in res1} == {"S1"}

    res2 = bd.buscar_servicios_por_camara("gral. san martin")
    assert {s.nombre for s in res2} == {"S3"}

    # Caso con abreviaturas y acentos que antes causaba falso negativo
    camara = "Cra Av. Gral Juan Domingo Per\u00f3n 7540 BENAVIDEZ"
    bd.crear_servicio(nombre="S4", cliente="D", camaras=[camara])

    # La búsqueda debería funcionar aunque se omitan los acentos
    res3 = bd.buscar_servicios_por_camara("peron 7540")
    assert {s.nombre for s in res3} == {"S4"}


    bd.crear_servicio(nombre="S5", cliente="E", camaras=["Cámara Fiscalía"])
    res4 = bd.buscar_servicios_por_camara("camara fiscalia")
    assert {s.nombre for s in res4} == {"S5"}


def test_buscar_servicios_por_camara_jsonb():
    """Verifica la búsqueda cuando ``camaras`` se almacena como JSONB."""
    bd.crear_servicio(nombre="SJ1", cliente="G", camaras=["Cámara JSONB"])

    res = bd.buscar_servicios_por_camara("camara jsonb")
    assert {s.nombre for s in res} == {"SJ1"}



def test_exportar_camaras_servicio(tmp_path):
    servicio = bd.crear_servicio(
        nombre="S4", cliente="D", camaras=["Camara 1", "Camara 2"]
    )

    ruta = tmp_path / "camaras.xlsx"
    ok = bd.exportar_camaras_servicio(servicio.id, str(ruta))
    assert ok is True
    assert ruta.exists()

    wb = openpyxl.load_workbook(ruta)
    ws = wb.active
    filas = [c[0].value for c in ws.iter_rows(values_only=False)]
    assert filas == ["camara", "Camara 1", "Camara 2"]


def test_actualizar_tracking_jsonb():
    servicio = bd.crear_servicio(nombre="S6", cliente="F")
    bd.actualizar_tracking(servicio.id, "ruta.txt", ["C1"], ["t1.txt"])

    with bd.SessionLocal() as s:
        reg = s.get(bd.Servicio, servicio.id)
        assert reg.ruta_tracking == "ruta.txt"
        assert reg.camaras == ["C1"]
        assert reg.trackings == ["t1.txt"]


def test_actualizar_tracking_string():
    """Verifica que se actualice si el campo ``trackings`` quedó como texto."""
    servicio = bd.crear_servicio(nombre="S7", cliente="G", trackings="[]")
    bd.actualizar_tracking(servicio.id, trackings_txt=["nuevo.txt"])

    with bd.SessionLocal() as s:
        reg = s.get(bd.Servicio, servicio.id)
        assert reg.trackings == ["nuevo.txt"]


def test_crear_ingreso():
    servicio = bd.crear_servicio(nombre="S5", cliente="E")
    fecha = datetime(2023, 1, 1, 12, 30)
    ingreso = bd.crear_ingreso(servicio.id, "Camara X", fecha=fecha, usuario="u")
    with bd.SessionLocal() as session:
        fila = session.query(bd.Ingreso).first()
        assert fila.camara == "Camara X"
        assert fila.fecha == fecha


def test_registrar_servicio_merge():
    """Verifica que ``registrar_servicio`` no duplique filas."""
    bd.crear_servicio(id=100, nombre="n1", cliente="a")
    bd.registrar_servicio(100, "c1")
    bd.registrar_servicio(100, "c1")
    with bd.SessionLocal() as session:
        filas = session.query(bd.Servicio).filter(bd.Servicio.id == 100).all()
        assert len(filas) == 1
        assert filas[0].id_carrier == "c1"

