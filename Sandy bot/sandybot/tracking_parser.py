"""Parser de trackings de fibra óptica."""

from __future__ import annotations

import os
import re
from typing import List, Tuple

import pandas as pd


class TrackingParser:
    """Procesa archivos de tracking para detectar cámaras comunes."""

    def __init__(self) -> None:
        self._data: List[Tuple[str, pd.DataFrame]] = []

    def _sanitize_sheet_name(self, name: str) -> str:
        """Limpia el nombre de la hoja para que sea válida en Excel."""
        cleaned = re.sub(r"[\\/*?\[\]]", "_", name)
        return cleaned[:31]

    def parse_file(self, path: str, sheet_name: str | None = None) -> None:
        """Lee un archivo de texto y guarda sus datos en memoria."""
        registros: List[Tuple[str, str]] = []
        distancia_prev = ""

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Capturar distancia previa
                match_dist = re.search(r"\*\s*(\d+(?:\.\d+)?)\s*mts", line, re.I)
                if match_dist:
                    distancia_prev = match_dist.group(1)
                    continue

                # Capturar línea de empalme
                match_emp = re.search(r"^Empalme\s+\d+\s*:\s*(.+)", line)
                if match_emp:
                    camara = match_emp.group(1).strip()
                    registros.append((camara, distancia_prev))

        df = pd.DataFrame(registros, columns=["camara", "distancia"])
        if sheet_name is None:
            sheet_name = os.path.splitext(os.path.basename(path))[0]
        sheet = self._sanitize_sheet_name(sheet_name)
        self._data.append((sheet, df))

    def clear_data(self) -> None:
        """Elimina cualquier información almacenada previamente."""
        self._data.clear()

    def _find_common_chambers(self) -> List[str]:
        """Obtiene las cámaras presentes en todos los trackings."""
        if not self._data:
            return []
        sets = [set(df["camara"].astype(str)) for _, df in self._data]
        comunes = set.intersection(*sets)
        return sorted(comunes)

    def generate_excel(self, output: str) -> None:
        """Genera un Excel con cada tracking y las coincidencias."""
        coincidencias = pd.DataFrame(
            self._find_common_chambers(), columns=["camara"]
        )
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet, df in self._data:
                df.to_excel(writer, sheet_name=sheet, index=False)
            coincidencias.to_excel(writer, sheet_name="Coincidencias", index=False)
            