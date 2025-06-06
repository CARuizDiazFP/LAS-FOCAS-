import sys
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "Sandy bot"))

from sandybot.tracking_parser import TrackingParser


def _crear_archivo(tmp_path: Path, nombre: str, lineas: list[str]) -> Path:
    archivo = tmp_path / nombre
    archivo.write_text("\n".join(lineas), encoding="utf-8")
    return archivo


def test_parse_file_y_generar_excel(tmp_path):
    lineas1 = [
        "* 10 mts",
        "Empalme 1: Camara A",
        "* 20 mts",
        "Empalme 2: Camara B",
    ]
    lineas2 = [
        "* 5 mts",
        "Empalme 1: Camara B",
        "* 15 mts",
        "Empalme 2: Camara C",
    ]
    archivo1 = _crear_archivo(tmp_path, "t1.txt", lineas1)
    archivo2 = _crear_archivo(tmp_path, "t2.txt", lineas2)

    parser = TrackingParser()
    parser.parse_file(str(archivo1))
    parser.parse_file(str(archivo2))

    assert len(parser._data) == 2
    for _, df in parser._data:
        assert list(df.columns) == ["camara", "distancia"]

    salida = tmp_path / "resultado.xlsx"
    parser.generate_excel(str(salida))
    assert salida.exists()

    with pd.ExcelFile(salida) as xls:
        nombres = xls.sheet_names
        for hoja, _ in parser._data:
            assert hoja in nombres
        assert "Coincidencias" in nombres
        coinc_df = pd.read_excel(xls, sheet_name="Coincidencias")
        assert "Camara B" in coinc_df["camara"].tolist()
