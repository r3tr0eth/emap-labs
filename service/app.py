"""emap-labs semantic service — el retriever híbrido como servicio HTTP.

Corre en el VPS (patrón OTP): emap-next (Vercel) hace proxy vía
EMAP_SEMANTIC_URL. Sin base de datos: 13 vectores de categoría en memoria
+ búsqueda estructurada sobre los POIs cargados al arrancar.

    EMAP_DATA_DIR=/opt/emap-labs/data uvicorn app:app --port 8083

Validación: híbrido en held-out ES 79% / EU 72% (evals/, 2026-07-07).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Query

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
from semantic_local import HybridRetriever  # noqa: E402

from emap_geo.distance import haversine_m  # noqa: E402

DATA_DIR = Path(os.environ.get("EMAP_DATA_DIR", "../emap-next/data")).resolve()

# mismo layout que emap-next/data (rsync tal cual)
LAYER_FILES = {
    "fountains": "pois-euskadi/fountains.json",
    "toilets": "pois-euskadi/toilets.json",
    "parking": "pois-euskadi/parking.json",
    "bikepark": "pois-euskadi/bikepark.json",
    "defib": "pois-euskadi/defib.json",
    "beaches": "pois-euskadi/beaches.json",
    "ev": "processed/pois/ev.json",
    "cameras": "processed/pois/cameras.json",
    "metro": "processed/pois/metro.json",
    "euskotren": "processed/pois/euskotren.json",
    "cercanias": "processed/pois/cercanias.json",
    "bilbobus": "processed/pois/bilbobus.json",
    "bizkaibus": "processed/pois/bizkaibus.json",
}

app = FastAPI(title="emap-labs semantic", version="0.1")
_retriever: HybridRetriever | None = None
_counts: dict[str, int] = {}
_datasets: dict[str, list[dict]] = {}
_units: list[dict] = []  # barrios/distritos/municipios con anillos (lat,lon)


@app.on_event("startup")
def load() -> None:
    global _retriever
    datasets = {}
    for layer, rel in LAYER_FILES.items():
        path = DATA_DIR / rel
        if path.is_file():
            datasets[layer] = json.loads(path.read_text())["pois"]
            _counts[layer] = len(datasets[layer])
        else:
            print(f"aviso: falta {path}", file=sys.stderr)
    _retriever = HybridRetriever(datasets)
    _retriever.set_anchor_names([])
    _datasets.update(datasets)
    nb = DATA_DIR / "processed/neighborhoods/neighborhoods.json"
    if nb.is_file():
        for f in json.loads(nb.read_text())["features"]:
            rings = [[(p[1], p[0]) for p in poly[0]]
                     for poly in f["geometry"]["coordinates"]]
            lats = [p[0] for r in rings for p in r]
            lons = [p[1] for r in rings for p in r]
            _units.append({"props": f["properties"], "rings": rings,
                           "bbox": (min(lats), min(lons), max(lats), max(lons))})
    print(f"semantic listo: {sum(_counts.values())} POIs en {len(_counts)} capas, "
          f"{len(_units)} unidades administrativas")


@app.get("/healthz")
def healthz():
    return {"ok": _retriever is not None, "layers": _counts,
            "pois": sum(_counts.values()), "retriever": _retriever and _retriever.name}


@app.get("/search")
def search(
    q: str = Query(min_length=1, max_length=200),
    lat: float | None = None,
    lon: float | None = None,
    k: int = Query(default=5, ge=1, le=20),
):
    t0 = time.monotonic()
    anchor = {"lat": lat, "lon": lon} if lat is not None and lon is not None else None
    results = _retriever.retrieve(q, anchor, k=k)
    out = []
    for r in results:
        item = {"id": r["id"], "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                "layer": r["layer"], "tags": r.get("tags") or {}}
        if anchor:
            item["distance_m"] = round(haversine_m(lat, lon, r["lat"], r["lon"]))
        out.append(item)
    return {
        "query": q,
        "abstained": not out,  # no inventamos: sin categoría clara, vacío
        "results": out,
        "retriever": _retriever.name,
        "took_ms": round((time.monotonic() - t0) * 1000),
        "attribution": "© OpenStreetMap contributors (ODbL) · Open Data Euskadi",
    }


RAIL = ("metro", "euskotren", "cercanias")
BUS = ("bilbobus", "bizkaibus")
KIND_RANK = {"neighborhood": 0, "district": 1, "municipality": 2}


def _nearest(layers: tuple[str, ...], lat: float, lon: float):
    best = None
    for layer in layers:
        for p in _datasets.get(layer, []):
            d = haversine_m(lat, lon, p["lat"], p["lon"])
            if best is None or d < best[0]:
                best = (d, p, layer)
    if best is None:
        return None
    return {"name": best[1]["name"], "layer": best[2], "distance_m": round(best[0])}


@app.get("/explain")
def explain(lat: float, lon: float):
    """Hechos del entorno de un punto — descriptivo, sin juicios (ETICA-DATOS)."""
    from emap_geo.polygon import point_in_polygon

    unit = None
    for u in _units:
        b = u["bbox"]
        if not (b[0] <= lat <= b[2] and b[1] <= lon <= b[3]):
            continue
        if any(point_in_polygon(lat, lon, r) for r in u["rings"]):
            if unit is None or KIND_RANK[u["props"]["kind"]] < KIND_RANK[unit["kind"]]:
                unit = u["props"]
    counts = {}
    for layer in ("fountains", "toilets", "bikepark", "defib"):
        counts[layer] = sum(
            1 for p in _datasets.get(layer, [])
            if haversine_m(lat, lon, p["lat"], p["lon"]) < 300)
    return {
        "unit": unit and {"name": unit["name"], "kind": unit["kind"],
                          "parent": unit.get("parent")},
        "nearest_rail": _nearest(RAIL, lat, lon),
        "nearest_bus": _nearest(BUS, lat, lon),
        "nearest_toilet": _nearest(("toilets",), lat, lon),
        "counts_300m": counts,
        "attribution": "© OpenStreetMap contributors (ODbL) · Open Data Euskadi",
    }
