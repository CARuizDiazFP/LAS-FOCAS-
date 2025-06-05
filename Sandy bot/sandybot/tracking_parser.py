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
        """Limpia el nombre de la hoja para que sea válido en Excel."""
        cleaned = re.sub(r"[\\/*?\[\]]", "_", name)
        return cleaned[:31]

    def parse_file(self, path: str) -> None:
        """Lee un archivo de texto y guarda sus datos en memoria."""
        with open(path, "r", encoding="utf-8") as f:
            registros: List[Tuple[str, str]] = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Dividir por punto y coma o tabulación si existen, de lo
                # contrario usar el primer espacio como separador.
                if ";" in line or "\t" in line:
                    partes = re.split(r"[;\t]", line)
                else:
                    partes = re.split(r"\s+", line, maxsplit=2)
                partes = [p.strip() for p in partes if p.strip()]
                camara = partes[0] if partes else ""
                distancia = partes[1] if len(partes) > 1 else ""
                registros.append((camara, distancia))

        df = pd.DataFrame(registros, columns=["camara", "distancia"])
        nombre_archivo = os.path.splitext(os.path.basename(path))[0]
        sheet = self._sanitize_sheet_name(nombre_archivo)
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
        coincidencias = pd.DataFrame(self._find_common_chambers(), columns=["camara"])
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet, df in self._data:
                df.to_excel(writer, sheet_name=sheet, index=False)
            coincidencias.to_excel(writer, sheet_name="Coincidencias", index=False)

