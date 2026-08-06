"""Planificador de rutas accesibles.

Calcula rutas a pie que minimizan barreras para:
- silla de ruedas
- carrito infantil
- movilidad reducida temporal

Fuentes:
- OSRM (:8085): routing a pie (evita autopistas, etc.)
- OSM Overpass: ascensores, escaleras, aseos adaptados (cuando disponible)
- Datos locales: POIs con tags de accesibilidad
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("EMAP_DATA_DIR", "/opt/emap-labs/data")).resolve()
OSRM_BASE = os.environ.get("EMAP_OSRM_URL", "http://localhost:8085")

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def osrm_route(from_lat: float, from_lon: float,
               to_lat: float, to_lon: float,
               profile: str = "foot") -> dict | None:
    """Calcula ruta con OSRM. profile: foot, bike, car."""
    url = f"{OSRM_BASE}/route/v1/{profile}/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson&steps=true"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") == "Ok":
            return data["routes"][0]
    except Exception:
        pass
    return None


def fetch_overpass(query: str, timeout: int = 30) -> dict | None:
    """Consulta Overpass con fallback entre mirrors."""
    for mirror in OVERPASS:
        try:
            data = urllib.parse.urlencode({"data": query}).encode()
            req = urllib.request.Request(mirror, data=data,
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            continue
    return None


def find_accessible_pois(bbox: tuple[float, float, float, float],
                         poi_type: str = "toilets") -> list[dict]:
    """Busca POIs accesibles en un bbox. Tipos: toilets, elevator, pharmacy."""
    min_lat, min_lon, max_lat, max_lon = bbox

    if poi_type == "toilets":
        query = (f'[out:json][timeout:30];(node["amenity"="toilets"]["wheelchair"="yes"]'
                 f'({min_lat},{min_lon},{max_lat},{max_lon}););out body;')
    elif poi_type == "elevator":
        query = (f'[out:json][timeout:30];(node["highway"="elevator"]'
                 f'({min_lat},{min_lon},{max_lat},{max_lon}););out body;')
    elif poi_type == "pharmacy":
        query = (f'[out:json][timeout:30];(node["amenity"="pharmacy"]'
                 f'({min_lat},{min_lon},{max_lat},{max_lon}););out body;')
    else:
        return []

    doc = fetch_overpass(query)
    if not doc:
        return []

    results = []
    for el in doc.get("elements", []):
        if el.get("type") == "node" and el.get("lat"):
            results.append({
                "id": el["id"],
                "lat": el["lat"],
                "lon": el["lon"],
                "tags": el.get("tags", {}),
            })
    return results


def plan_accessible_route(
    from_lat: float, from_lon: float,
    to_lat: float, to_lon: float,
    profile: str = "wheelchair",
) -> dict:
    """Planifica una ruta accesible.

    Args:
        from_lat, from_lon: origen
        to_lat, to_lon: destino
        profile: wheelchair, stroller, reduced_mobility

    Returns:
        dict con ruta y metadatos de accesibilidad
    """
    t0 = time.monotonic()

    # Calcular bbox para buscar POIs de accesibilidad cercanos
    min_lat = min(from_lat, to_lat) - 0.01
    max_lat = max(from_lat, to_lat) + 0.01
    min_lon = min(from_lon, to_lon) - 0.01
    max_lon = max(from_lon, to_lon) + 0.01

    # Buscar infraestructura accesible cercana (ascensores, aseos)
    elevators = find_accessible_pois((min_lat, min_lon, max_lat, max_lon), "elevator")
    accessible_toilets = find_accessible_pois((min_lat, min_lon, max_lat, max_lon), "toilets")

    # Calcular ruta a pie (más accesible que coche)
    route = osrm_route(from_lat, from_lon, to_lat, to_lon, profile="foot")

    if not route:
        return {
            "ok": False,
            "reason": "no_route_found",
            "profile": profile,
        }

    distance_m = route["distance"]
    duration_min = route["duration"] / 60

    # Extraer pasos para analizar barreras
    steps = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            steps.append({
                "name": step.get("name", ""),
                "distance_m": step.get("distance", 0),
                "duration_s": step.get("duration", 0),
                "maneuver": step.get("maneuver", {}).get("type", ""),
            })

    # Evaluar accesibilidad de la ruta
    assessment = assess_routeAccessibility(steps, profile)

    return {
        "ok": True,
        "profile": profile,
        "distance_m": int(distance_m),
        "duration_min": int(duration_min),
        "steps_count": len(steps),
        "geometry": route.get("geometry"),
        "accessibility": assessment,
        "nearby_elevators": len(elevators),
        "nearby_accessible_toilets": len(accessible_toilets),
        "took_ms": int((time.monotonic() - t0) * 1000),
        "caveats": [
            "Ruta a pie calculada con OSRM (sin datos de pendientes locales)",
            "Información de accesibilidad de OSM puede estar incompleta",
            "Verificar in situ antes de emprender el recorrido",
        ],
    }


def assess_routeAccessibility(steps: list[dict], profile: str) -> dict:
    """Evalúa la accesibilidad de una ruta basada en sus pasos."""
    issues = []
    score = 100

    for step in steps:
        name = step.get("name", "").lower()

        # Detectar posibles barreras por nombre de vía
        if any(t in name for t in ["escalera", "escaleras", "stairs", "step"]):
            issues.append(f"Posible escalera en: {name[:40]}")
            score -= 20 if profile == "wheelchair" else 10

        if any(t in name for t in ["cuesta", "pendiente", "ramp"]):
            issues.append(f"Posible pendiente en: {name[:40]}")
            score -= 10 if profile == "wheelchair" else 5

        # Pasos muy largos sin descanso
        if step.get("distance_m", 0) > 500:
            issues.append(f"Tramo largo sin descanso: {step['distance_m']:.0f}m")
            score -= 5

    # Clasificar
    if score >= 80:
        level = "good"
    elif score >= 60:
        level = "moderate"
    else:
        level = "poor"

    return {
        "score": max(0, score),
        "level": level,
        "issues": issues[:5],  # top 5 issues
        "recommendation": _accessibility_recommendation(level, profile),
    }


def _accessibility_recommendation(level: str, profile: str) -> str:
    """Genera recomendación según nivel de accesibilidad."""
    if level == "good":
        return "Ruta probablemente accesible. Verificar in situ."
    elif level == "moderate":
        return "Ruta con posibles dificultades. Considerar alternativas."
    else:
        if profile == "wheelchair":
            return "Ruta con barreras probables. No recomendada sin verificación."
        return "Ruta con dificultades. Considerar transporte alternativo."
