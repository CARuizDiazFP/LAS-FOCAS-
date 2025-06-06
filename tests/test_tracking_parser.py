import sys
import os
import importlib
from types import ModuleType
from pathlib import Path
import tempfile

# Crear un stub de pandas para evitar dependencias externas
pandas_stub = ModuleType("pandas")

class DataFrame:
    def __init__(self, registros=None, columns=None):
        self._data = {c: [] for c in (columns or [])}
        if registros:
            for fila in registros:
                for c, valor in zip(columns, fila):
                    self._data[c].append(valor)

    def __getitem__(self, columna):
        valores = self._data[columna]

        class Serie(list):
            def astype(self, _):
                return [str(v) for v in valores]

        return Serie(valores)

    def to_excel(self, writer, sheet_name=None, index=False):
        writer.write(sheet_name, self._data)

class ExcelWriter:
    def __init__(self, path, engine=None):
        self.path = path
        self.sheets = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        with open(self.path, "w", encoding="utf-8") as f:
            for nombre in self.sheets:
                f.write(f"{nombre}\n")

    def write(self, sheet_name, data):
        self.sheets[sheet_name] = data

pandas_stub.DataFrame = DataFrame
pandas_stub.ExcelWriter = ExcelWriter
sys.modules.setdefault("pandas", pandas_stub)

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

    with open(ruta_excel, "r", encoding="utf-8") as f:
        contenido_excel = f.read().splitlines()
    assert "Coincidencias" in contenido_excel

    os.remove(ruta_excel)
