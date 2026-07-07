#!/usr/bin/env python3
"""Score de barrio v1 (roadmap L2.1) → emap-next/data/processed/neighborhoods/scores.json

Agrega las señales locales disponibles por unidad administrativa
(barrio/distrito/municipio de neighborhoods.json) y produce componentes
EXPLICABLES 0-100 como percentil dentro de su grupo (kind) — un barrio
compite con barrios, un municipio con municipios:

  services  fuentes + aseos + DEA por km²
  mobility  paradas de transporte por km² (ferroviario ×3, bus ×1)
  cycling   km de bidegorri por km² + aparcabicis por km²
  calm      inverso de incidencias de tráfico históricas por km²
            (PROXY de tráfico, no ruido medido — no se finge)

score = media de componentes. Los conteos crudos se incluyen siempre:
el número manda, el score solo ordena.

Ejecutar con el venv de emap-next:
    ../emap-next/.venv/bin/python datasets/neighborhood-scores/build.py
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from emap_geo.distance import haversine_m
from emap_geo.polygon import point_in_polygon

LABS = Path(__file__).resolve().parents[2]
NEXT = (LABS / ".." / "emap-next").resolve()
OUT = NEXT / "data" / "processed" / "neighborhoods" / "scores.json"

POI_FILES = {
    "fountains": "data/pois-euskadi/fountains.json",
    "toilets": "data/pois-euskadi/toilets.json",
    "defib": "data/pois-euskadi/defib.json",
    "bikepark": "data/pois-euskadi/bikepark.json",
    "metro": "data/processed/pois/metro.json",
    "euskotren": "data/processed/pois/euskotren.json",
    "cercanias": "data/processed/pois/cercanias.json",
    "bilbobus": "data/processed/pois/bilbobus.json",
    "bizkaibus": "data/processed/pois/bizkaibus.json",
}
RAIL = {"metro", "euskotren", "cercanias"}
BUS = {"bilbobus", "bizkaibus"}


def load_units() -> list[dict]:
    fc = json.loads((NEXT / "data/processed/neighborhoods/neighborhoods.json").read_text())
    units = []
    for f in fc["features"]:
        rings = [poly[0] for poly in f["geometry"]["coordinates"]]  # outers, [lon,lat]
        latlon = [[(p[1], p[0]) for p in r] for r in rings]
        lats = [p[0] for r in latlon for p in r]
        lons = [p[1] for r in latlon for p in r]
        units.append({
            "props": f["properties"],
            "rings": latlon,
            "bbox": (min(lats), min(lons), max(lats), max(lons)),
        })
    return units


def area_km2(rings: list[list[tuple[float, float]]]) -> float:
    """Shoelace plano con corrección cos(lat) — suficiente a escala municipal."""
    total = 0.0
    for ring in rings:
        mean_lat = sum(p[0] for p in ring) / len(ring)
        kx = 111.320 * math.cos(math.radians(mean_lat))  # km/grado lon
        ky = 110.574                                      # km/grado lat
        s = 0.0
        for (lat1, lon1), (lat2, lon2) in zip(ring, ring[1:]):
            s += (lon1 * kx) * (lat2 * ky) - (lon2 * kx) * (lat1 * ky)
        total += abs(s) / 2
    return total


def inside(unit: dict, lat: float, lon: float) -> bool:
    b = unit["bbox"]
    if not (b[0] <= lat <= b[2] and b[1] <= lon <= b[3]):
        return False
    return any(point_in_polygon(lat, lon, ring) for ring in unit["rings"])


def percentile(values: list[float]) -> list[float]:
    """Percentil 0-100 de cada valor dentro de su lista (empates promedian)."""
    if len(values) < 2:
        return [50.0] * len(values)
    order = sorted(values)
    n = len(values)
    out = []
    for v in values:
        below = sum(1 for x in order if x < v)
        equal = sum(1 for x in order if x == v)
        out.append(round(100 * (below + (equal - 1) / 2) / (n - 1), 1))
    return out


def main() -> None:
    units = load_units()
    for u in units:
        u["area"] = max(area_km2(u["rings"]), 0.01)
        u["counts"] = {}

    # POIs y paradas
    for layer, rel in POI_FILES.items():
        pois = json.loads((NEXT / rel).read_text())["pois"]
        for u in units:
            u["counts"][layer] = sum(1 for p in pois if inside(u, p["lat"], p["lon"]))
        print(f"  {layer}: {len(pois)} puntos asignados")

    # bidegorris: longitud de tramos cuyo punto medio cae en la unidad
    bn = json.loads((NEXT / "data/raw/bike-network.json").read_text())["features"]
    for u in units:
        u["bike_km"] = 0.0
    for seg in bn:
        coords = seg["geometry"]["coordinates"]  # [lon, lat]
        if len(coords) < 2:
            continue
        length = sum(haversine_m(a[1], a[0], b[1], b[0])
                     for a, b in zip(coords, coords[1:])) / 1000
        mid = coords[len(coords) // 2]
        for u in units:
            if inside(u, mid[1], mid[0]):
                u["bike_km"] += length
    print(f"  bidegorris: {len(bn)} tramos asignados")

    # incidencias históricas de tráfico
    cells = json.loads((NEXT / "data/raw/traffic-patterns.json").read_text())["cells"]
    for u in units:
        u["traffic"] = sum(c["total"] for c in cells if inside(u, c["lat"], c["lon"]))
    print(f"  tráfico: {len(cells)} celdas asignadas")

    # componentes como percentil dentro de cada kind
    for kind in ("neighborhood", "district", "municipality"):
        group = [u for u in units if u["props"]["kind"] == kind]
        if not group:
            continue
        dens = lambda fn: [fn(u) / u["area"] for u in group]  # noqa: E731
        comp = {
            "services": percentile(dens(lambda u: u["counts"]["fountains"]
                                        + u["counts"]["toilets"] + u["counts"]["defib"])),
            "mobility": percentile(dens(lambda u: 3 * sum(u["counts"][l] for l in RAIL)
                                        + sum(u["counts"][l] for l in BUS))),
            "cycling": percentile(dens(lambda u: u["bike_km"]
                                       + 0.1 * u["counts"]["bikepark"])),
            "calm": percentile([-x for x in dens(lambda u: u["traffic"])]),
        }
        for i, u in enumerate(group):
            u["components"] = {k: v[i] for k, v in comp.items()}
            u["score"] = round(sum(u["components"].values()) / len(comp), 1)

    out = {
        "meta": {
            "generated": date.today().isoformat(),
            "generator": "emap-labs/datasets/neighborhood-scores/build.py",
            "method": "componentes = percentil de densidad por km² dentro de su kind; "
                      "score = media. calm es proxy de incidencias de tráfico "
                      "históricas, no ruido medido.",
            "sources": "OSM (ODbL), GTFS oficiales, incidencias tráfico Euskadi (harvest propio)",
        },
        "scores": [{
            "id": u["props"]["id"], "name": u["props"]["name"],
            "kind": u["props"]["kind"], "parent": u["props"].get("parent"),
            "area_km2": round(u["area"], 2),
            "counts": u["counts"],
            "bike_km": round(u["bike_km"], 2),
            "traffic_incidents": u["traffic"],
            "components": u["components"],
            "score": u["score"],
        } for u in units],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False) + "\n")
    print(f"OK → {OUT} ({OUT.stat().st_size // 1024} KB, {len(units)} unidades)")

    barrios = sorted((u for u in units if u["props"]["kind"] == "neighborhood"),
                     key=lambda u: -u["score"])
    print("\ntop 5 barrios:", [(b["props"]["name"]["es"], b["score"]) for b in barrios[:5]])
    print("cola 3 barrios:", [(b["props"]["name"]["es"], b["score"]) for b in barrios[-3:]])


if __name__ == "__main__":
    main()
