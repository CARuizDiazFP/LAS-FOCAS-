# Nombre de archivo: geo_utils.py
# Ubicación de archivo: Sandy bot/sandybot/geo_utils.py
# User-provided custom instructions
"""Funciones para trabajar con coordenadas geográficas."""

from __future__ import annotations

import re
from typing import Iterable

try:
    import matplotlib.pyplot as plt
except Exception as e:  # pragma: no cover - importa al ejecutar
    plt = None


def extraer_coordenada(texto: str) -> tuple[float, float] | None:
    """Obtiene la primera coordenada válida dentro de ``texto``."""
    if not texto:
        return None
    limpio = re.sub(r"(?i)geo[:\s]*", "", texto)
    limpio = limpio.replace("--", "-")
    patron = re.compile(r"(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)")
    m = patron.search(limpio)
    if not m:
        return None
    lat, lon = m.groups()
    lat = lat.strip()
    lon = lon.strip()
    if re.match(r"^34", lat):
        lat = "-" + lat
    if re.match(r"^58", lon):
        lon = "-" + lon
    if not re.match(r"^-34", lat) or not re.match(r"^-58", lon):
        return None
    try:
        return float(lat), float(lon)
    except ValueError:
        return None


def generar_mapa_puntos(puntos: Iterable[tuple[float, float]], linea: str, ruta: str) -> None:
    """Genera un mapa PNG con ``puntos`` etiquetados por ``linea``."""
    if plt is None:
        raise RuntimeError("matplotlib no está disponible")

    lats, lons = zip(*puntos)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(lons, lats, color="red")
    for x, y in zip(lons, lats):
        ax.text(
            x,
            y,
            linea,
            ha="center",
            va="center",
            color="white",
            fontsize=8,
            bbox=dict(boxstyle="circle", facecolor="blue"),
        )
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(ruta, dpi=150)
    plt.close(fig)
