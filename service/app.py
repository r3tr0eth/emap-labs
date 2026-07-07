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
    print(f"semantic listo: {sum(_counts.values())} POIs en {len(_counts)} capas")


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
