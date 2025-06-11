# + Nombre de archivo: test_tracking_parser.py
# + Ubicación de archivo: tests/test_tracking_parser.py
# User-provided custom instructions
import sys
import os
import importlib
from pathlib import Path
import tempfile
import openpyxl



ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))


tracking_parser = importlib.import_module("sandybot.tracking_parser")
TrackingParser = tracking_parser.TrackingParser


def test_parse_and_generate_excel(tmp_path):
    contenido = (
        "* 10 mts\n"
        "Empalme 1: Camara A\n"
        "* 20 mts\n"
        "Empalme 2: Camara B\n"
    )
    archivo = tmp_path / "tracking.txt"
    archivo.write_text(contenido, encoding="utf-8")

    parser = TrackingParser()
    parser.parse_file(str(archivo))

    assert len(parser._data) == 1
    df = parser._data[0][1]
    assert list(df["camara"]) == ["Camara A", "Camara B"]

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_excel:
        parser.generate_excel(tmp_excel.name)
        ruta_excel = tmp_excel.name

    wb = openpyxl.load_workbook(ruta_excel)
    assert "Coincidencias" in wb.sheetnames

    os.remove(ruta_excel)
