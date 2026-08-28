"""Isócronas: áreas alcanzables en X minutos.

Usa OSRM table service para calcular duraciones a múltiples puntos
y construir contornos de isócrona. Cruza con infraestructura para
responder "qué servicios hay en 15 minutos".
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from regions import load_territory, resolve_layer_path

DATA_DIR = Path(os.environ.get("EMAP_DATA_DIR", "/opt/emap-labs/data")).resolve()
TERRITORY = load_territory(os.environ.get("EMAP_TERRITORY", "euskadi"))
OSRM_BASE = os.environ.get("EMAP_OSRM_URL", "http://localhost:5000")

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def osrm_table(from_lat: float, from_lon: float,
               destinations: list[tuple[float, float]],
               profile: str = "car") -> list[float] | None:
    """Calcula duraciones desde origen a múltiples destinos.

    Args:
        from_lat, from_lon: origen
        destinations: lista de (lat, lon) destinos
        profile: car, foot, bike

    Returns:
        Lista de duraciones en segundos (None si no hay ruta)
    """
    if not destinations:
        return []

    coords = f"{from_lon},{from_lat}"
    for lat, lon in destinations:
        coords += f";{lon},{lat}"

    url = (f"{OSRM_BASE}/table/v1/{profile}/{coords}"
           f"?sources=0&annotations=duration")
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") == "Ok":
            durations = data.get("durations", [[]])[0]
            return durations
    except Exception:
        pass
    return None


def generate_grid(center_lat: float, center_lon: float,
                  radius_km: float, n_points: int = 24) -> list[tuple[float, float]]:
    """Genera puntos en una grilla circular alrededor del centro."""
    points = []
    for r in range(1, n_points // 2 + 1):
        radius = radius_km * r / (n_points // 2)
        n_circle = max(8, int(2 * math.pi * r * 4))
        for i in range(n_circle):
            angle = 2 * math.pi * i / n_circle
            dlat = radius / 111 * math.cos(angle)
            dlon = radius / (111 * math.cos(math.radians(center_lat))) * math.sin(angle)
            points.append((center_lat + dlat, center_lon + dlon))
    return points


def compute_isochrone(lat: float, lon: float,
                      minutes: int = 15,
                      profile: str = "car") -> dict:
    """Calcula isócrona: puntos alcanzables en X minutos.

    Args:
        lat, lon: origen
        minutes: presupuesto de tiempo
        profile: car, foot, bike

    Returns:
        GeoJSON-like dict con contornos + estadísticas
    """
    t0 = time.monotonic()

    # Radio máximo estimado según modo
    speeds = {"car": 30, "foot": 5, "bike": 15}  # km/h promedio
    max_radius = speeds.get(profile, 30) * (minutes / 60) * 1.2  # +20% margen

    # Generar grilla de puntos
    grid = generate_grid(lat, lon, max_radius, n_points=20)

    # Calcular duraciones con OSRM
    durations = osrm_table(lat, lon, grid, profile)

    if not durations:
        return {
            "ok": False,
            "reason": "osrm_error",
            "profile": profile,
            "minutes": minutes,
        }

    # Puntos dentro del presupuesto
    reachable = []
    for i, dur in enumerate(durations):
        if dur is not None and dur <= minutes * 60:
            reachable.append({
                "lat": grid[i][0],
                "lon": grid[i][1],
                "duration_min": round(dur / 60, 1),
            })

    # Construir contorno convexo simplificado (alpha shape básico)
    hull = _convex_hull([(p["lon"], p["lat"]) for p in reachable])

    return {
        "ok": True,
        "profile": profile,
        "minutes": minutes,
        "origin": {"lat": lat, "lon": lon},
        "reachable_points": len(reachable),
        "total_points": len(grid),
        "coverage_pct": round(len(reachable) / len(grid) * 100, 1) if grid else 0,
        "hull": hull,
        "took_ms": int((time.monotonic() - t0) * 1000),
    }


def _convex_hull(points: list[tuple[float, float]]) -> list[dict]:
    """Calcula el convex hull de un conjunto de puntos (algoritmo Graham scan)."""
    if len(points) < 3:
        return [{"lon": p[0], "lat": p[1]} for p in points]

    # Ordenar por x, luego y
    points = sorted(set(points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # Lower hull
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Upper hull
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]
    return [{"lon": p[0], "lat": p[1]} for p in hull]


def find_pois_in_isochrone(lat: float, lon: float,
                           minutes: int,
                           profile: str = "car",
                           poi_layers: list[str] | None = None) -> dict:
    """Encuentra POIs dentro de una isócrona.

    Args:
        lat, lon: origen
        minutes: presupuesto de tiempo
        profile: car, foot, bike
        poi_layers: capas a buscar (default: infraestructura útil)

    Returns:
        Isócrona + POIs alcanzables
    """
    if poi_layers is None:
        poi_layers = ["fountains", "toilets", "pharmacy", "defib", "ev"]

    isochrone = compute_isochrone(lat, lon, minutes, profile)
    if not isochrone.get("ok"):
        return isochrone

    # Cargar POIs de las capas solicitadas
    all_pois = []
    for layer in poi_layers:
        path = _layer_path(layer)
        if not path or not path.exists():
            continue
        try:
            doc = json.loads(path.read_text())
            pois = doc.get("pois", [])
            for p in pois:
                all_pois.append({
                    "layer": layer,
                    "name": p.get("name", {}),
                    "lat": p["lat"],
                    "lon": p["lon"],
                    "tags": p.get("tags", {}),
                })
        except Exception:
            continue

    # Filtrar POIs dentro del hull
    hull = isochrone.get("hull", [])
    if hull and all_pois:
        reachable_pois = [
            p for p in all_pois
            if _point_in_polygon(p["lon"], p["lat"],
                                [(h["lon"], h["lat"]) for h in hull])
        ]
    else:
        reachable_pois = []

    isochrone["pois_found"] = len(reachable_pois)
    isochrone["pois"] = reachable_pois[:50]  # limitar respuesta
    isochrone["poi_layers_searched"] = poi_layers

    return isochrone


def _layer_path(layer: str) -> Path | None:
    """Resuelve ruta de una capa."""
    return resolve_layer_path(DATA_DIR, TERRITORY, layer)


def _point_in_polygon(x: float, y: float,
                      polygon: list[tuple[float, float]]) -> bool:
    """Ray casting algorithm para punto en polígono."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside
