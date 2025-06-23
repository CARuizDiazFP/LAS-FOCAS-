# Nombre de archivo: geo_utils.py
# Ubicación de archivo: Sandy bot/sandybot/geo_utils.py
# User-provided custom instructions
"""Funciones para trabajar con coordenadas geográficas."""

from __future__ import annotations

import re
from typing import Iterable
import geopandas as gpd
import contextily as ctx
from shapely.geometry import Point
import matplotlib.pyplot as plt



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


def generar_mapa_puntos(
    puntos: Iterable[tuple[float, float]],
    indices: Iterable[int],
    ruta: str,
) -> None:
    """Genera un mapa PNG con las coordenadas y sus números de fila."""

    gdf = gpd.GeoDataFrame(
        index=range(len(list(puntos))),
        geometry=[Point(lon, lat) for lat, lon in puntos],
        crs="EPSG:4326",
    ).to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(6, 6))
    gdf.plot(ax=ax, color="red")

    for numero, (x, y) in zip(indices, zip(gdf.geometry.x, gdf.geometry.y)):
        ax.text(
            x,
            y,
            str(numero),
            ha="center",
            va="center",
            color="white",
            fontsize=8,
            bbox=dict(boxstyle="circle", facecolor="blue"),
        )

    xmin, ymin, xmax, ymax = gdf.total_bounds
    base_m = 0.04 * 25000  # 4 cm a escala 1:25.000
    if len(gdf) == 1:
        cx, cy = gdf.geometry.x.iloc[0], gdf.geometry.y.iloc[0]
        ax.set_xlim(cx - base_m / 2, cx + base_m / 2)
        ax.set_ylim(cy - base_m / 2, cy + base_m / 2)
    else:
        width = xmax - xmin
        height = ymax - ymin
        width = max(width, base_m)
        height = max(height, base_m)
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        ax.set_xlim(cx - width / 2, cx + width / 2)
        ax.set_ylim(cy - height / 2, cy + height / 2)

    ctx.add_basemap(ax, crs="EPSG:3857", source=ctx.providers.OpenStreetMap.Mapnik)
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(ruta, dpi=150)
    plt.close()
