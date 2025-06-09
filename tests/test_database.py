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
