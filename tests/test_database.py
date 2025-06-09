import os
import sys
import importlib
from pathlib import Path
from datetime import datetime
import pytest
import openpyxl

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine
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
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "sandy"
}
os.environ.update(required_vars)

# Forzar que ``sandybot.database`` utilice SQLite en memoria
import sqlalchemy
orig_create_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: orig_create_engine("sqlite:///:memory:")

bd = importlib.import_module("sandybot.database")

sqlalchemy.create_engine = orig_create_engine
bd.SessionLocal = sessionmaker(bind=bd.engine)
bd.Base.metadata.create_all(bind=bd.engine)


def test_buscar_servicios_por_camara():
    bd.crear_servicio(nombre="S1", cliente="A", camaras=["Camara Central"])
    bd.crear_servicio(nombre="S2", cliente="B", camaras=["Nodo Secundario"])
    bd.crear_servicio(nombre="S3", cliente="C", camaras=["Avenida General San Martin"])

    res1 = bd.buscar_servicios_por_camara("camara central")
    assert {s.nombre for s in res1} == {"S1"}

    res2 = bd.buscar_servicios_por_camara("gral. san martin")
    assert {s.nombre for s in res2} == {"S3"}

    # Caso con abreviaturas y acentos que antes causaba falso negativo
    camara = "Cra Av. Gral Juan Domingo Per\u00f3n 7540 BENAVIDEZ"
    bd.crear_servicio(nombre="S4", cliente="D", camaras=[camara])

    # La búsqueda utiliza la misma cadena que se almacen\u00f3. Con la mejora,
    # debe encontrarse el servicio sin importar las diferencias de formato
    res3 = bd.buscar_servicios_por_camara(camara)
    assert {s.nombre for s in res3} == {"S4"}


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
