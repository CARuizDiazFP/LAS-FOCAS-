import os
import sys
import importlib
from pathlib import Path
import pytest

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
    "DB_HOST": "",
    "DB_PORT": "",
    "DB_NAME": ""
}
os.environ.update(required_vars)

# Importar módulo de base de datos y ajustar engine a SQLite
bd = importlib.import_module("sandybot.database")
engine = create_engine("sqlite:///:memory:")
bd.engine = engine
bd.SessionLocal = sessionmaker(bind=engine)
bd.Base.metadata.create_all(bind=engine)


def test_buscar_servicios_por_camara():
    bd.crear_servicio(nombre="S1", cliente="A", camaras=["C\u00e1mara Central"])
    bd.crear_servicio(nombre="S2", cliente="B", camaras=["Nodo Secundario"])
    bd.crear_servicio(nombre="S3", cliente="C", camaras=["Av. Gral. San Mart\u00edn"])

    res1 = bd.buscar_servicios_por_camara("camara central")
    assert {s.nombre for s in res1} == {"S1"}

    res2 = bd.buscar_servicios_por_camara("gral san martin")
    assert {s.nombre for s in res2} == {"S3"}
