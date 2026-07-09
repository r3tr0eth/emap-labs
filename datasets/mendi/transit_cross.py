#!/usr/bin/env python3
"""Cruce cimas × transporte público — "el monte en transporte público" v0.

Para cada cima de peaks.json, la parada/estación más cercana entre todas
las redes (metro, Euskotren, Cercanías, Bilbobus, Bizkaibus).

HONESTIDAD: distancia en LÍNEA RECTA (haversine), no ruta a pie — sirve
para rankear candidatas ("qué cimas tienen transporte cerca"), no para
prometer tiempos. El cómo-llegar real llegará con OTP (roadmap L5).

Escribe emap-next/data/processed/mendi/peaks-transit.json y se registra
en el manifest del data catalog.

Uso: ../emap-next/.venv/bin/python datasets/mendi/transit_cross.py
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

LABS = Path(__file__).resolve().parents[2]
NEXT_DATA = (LABS / ".." / "emap-next" / "data").resolve()
OUT = NEXT_DATA / "processed" / "mendi" / "peaks-transit.json"

STOP_LAYERS = ["metro", "euskotren", "cercanias", "bilbobus", "bizkaibus"]


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * (1 - math.cos((lon2 - lon1) * p)) / 2)
    return 12742000 * math.asin(math.sqrt(a))


def main() -> None:
    peaks = json.loads((NEXT_DATA / "pois-euskadi" / "peaks.json").read_text())["pois"]
    stops = []
    for layer in STOP_LAYERS:
        for s in json.loads((NEXT_DATA / "processed" / "pois" / f"{layer}.json").read_text())["pois"]:
            stops.append((layer, s["name"].get("es", ""), s["lat"], s["lon"]))

    items = []
    for p in peaks:
        best = min(stops, key=lambda s: haversine_m(p["lat"], p["lon"], s[2], s[3]))
        d = haversine_m(p["lat"], p["lon"], best[2], best[3])
        items.append({
            "peak": p["name"], "ele": p["tags"].get("ele"),
            "lat": p["lat"], "lon": p["lon"],
            "nearest_stop": {"layer": best[0], "name": best[1],
                             "dist_m": int(d)},
        })
    items.sort(key=lambda i: i["nearest_stop"]["dist_m"])

    within = lambda m: sum(1 for i in items if i["nearest_stop"]["dist_m"] <= m)  # noqa: E731
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": date.today().isoformat(),
        "source": "derivado: peaks.json (OSM) × paradas GTFS oficiales",
        "license": "ODbL 1.0 (agregado OSM + GTFS oficiales)",
        "method": ("distancia haversine en línea recta a la parada más "
                   "cercana — NO es ruta a pie ni tiempo; ranking de "
                   "candidatas hasta que OTP dé el cómo-llegar real"),
        "count": len(items),
        "summary": {"within_2km": within(2000), "within_5km": within(5000)},
        "items": items,
    }, ensure_ascii=False))
    print(f"→ {OUT}")
    print(f"cimas: {len(items)} · con parada ≤2 km: {within(2000)} · "
          f"≤5 km: {within(5000)}")
    print("5 más accesibles:", "; ".join(
        f"{i['peak']['es']} ({i['nearest_stop']['dist_m']} m de "
        f"{i['nearest_stop']['name']} [{i['nearest_stop']['layer']}])"
        for i in items[:5]))


if __name__ == "__main__":
    main()
