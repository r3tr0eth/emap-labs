"""emap-labs semantic service — el retriever híbrido como servicio HTTP.

Corre en el VPS (patrón OTP): emap-next (Vercel) hace proxy vía
EMAP_SEMANTIC_URL. Sin base de datos: 13 vectores de categoría en memoria
+ búsqueda estructurada sobre los POIs cargados al arrancar.

    EMAP_DATA_DIR=/opt/emap-labs/data uvicorn app:app --port 8083

Validación: híbrido en held-out ES 79% / EU 72% (evals/, 2026-07-07).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
from semantic_local import HybridRetriever  # noqa: E402
from fastembed.rerank.cross_encoder import TextCrossEncoder  # noqa: E402

from emap_geo.distance import haversine_m  # noqa: E402
from explain import explain_detection, explain_result, _load_source  # noqa: E402
from hike_planner import plan_hike  # noqa: E402
from accessibility import plan_accessible_route, find_accessible_pois  # noqa: E402
from isochrones import compute_isochrone, find_pois_in_isochrone  # noqa: E402
from data_freshness import quality_report, poi_freshness  # noqa: E402

DATA_DIR = Path(os.environ.get("EMAP_DATA_DIR", "../emap-next/data")).resolve()

# mismo layout que emap-next/data (rsync tal cual)
LAYER_FILES = {
    "fountains": "pois-euskadi/fountains.json",
    "toilets": "pois-euskadi/toilets.json",
    "parking": "pois-euskadi/parking.json",
    "bikepark": "pois-euskadi/bikepark.json",
    "defib": "pois-euskadi/defib.json",
    "beaches": "pois-euskadi/beaches.json",
    # euskadi-places (Open Data Euskadi, P1/P2 — 2026-07)
    "pharmacy": "pois-euskadi/pharmacy.json",
    "library": "pois-euskadi/library.json",
    "sports": "pois-euskadi/sports.json",
    "food": "pois-euskadi/food.json",
    "lodging": "pois-euskadi/lodging.json",
    "hostel": "pois-euskadi/hostel.json",
    "camping": "pois-euskadi/camping.json",
    "nature": "pois-euskadi/nature.json",
    "peaks": "pois-euskadi/peaks.json",
    "ev": "processed/pois/ev.json",
    "cameras": "processed/pois/cameras.json",
    "metro": "processed/pois/metro.json",
    "euskotren": "processed/pois/euskotren.json",
    "cercanias": "processed/pois/cercanias.json",
    "bilbobus": "processed/pois/bilbobus.json",
    "bizkaibus": "processed/pois/bizkaibus.json",
}

app = FastAPI(title="emap-labs semantic", version="0.2")
_retriever: HybridRetriever | None = None
_reranker: TextCrossEncoder | None = None
_counts: dict[str, int] = {}
_datasets: dict[str, list[dict]] = {}
_units: list[dict] = []  # barrios/distritos/municipios con anillos (lat,lon)


def _ensure_poi_id(poi: dict, layer: str, idx: int) -> dict:
    """Los POIs de euskadi-places no traen id: genera uno estable (<layer>:<idx>)
    para que el retriever y /search funcionen uniformemente."""
    if "id" not in poi:
        poi["id"] = f"{layer}:{idx}"
    return poi


@app.on_event("startup")
def load() -> None:
    global _retriever
    datasets = {}
    for layer, rel in LAYER_FILES.items():
        path = DATA_DIR / rel
        if path.is_file():
            raw = json.loads(path.read_text())["pois"]
            datasets[layer] = [_ensure_poi_id(p, layer, i) for i, p in enumerate(raw)]
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
    # Construir grupos para KD-tree (explain-place).
    _GROUP_LAYERS.update({"rail": RAIL, "bus": BUS, "toilets": ("toilets",)})
    # Reranker multilingüe (jina-reranker-v2). Modelo ONNX, ~1.1 GB en disco.
    _reranker = TextCrossEncoder("jinaai/jina-reranker-v2-base-multilingual")
    print(f"semantic listo: {sum(_counts.values())} POIs en {len(_counts)} capas, "
          f"{len(_units)} unidades administrativas, reranker cargado")


@app.get("/healthz")
def healthz():
    missing = [rel for layer, rel in LAYER_FILES.items()
               if not (DATA_DIR / rel).is_file()]
    degraded = [layer for layer in LAYER_FILES if layer not in _counts]
    return {
        "ok": _retriever is not None and not missing and not degraded,
        "layers": _counts,
        "pois": sum(_counts.values()),
        "retriever": _retriever and _retriever.name,
        "missing_files": missing,
        "degraded_layers": degraded,
        "expected_layers": len(LAYER_FILES),
        "loaded_layers": len(_counts),
    }


@app.get("/tts")
def tts(text: str = Query(..., min_length=1, max_length=280), lang: str = "eu"):
    """WAV de navegación. Solo euskera (Piper Maider). Sin modelo → 503, no se finge."""
    from tts import synthesize_eu

    low = (lang or "eu").lower()
    if not low.startswith("eu"):
        return JSONResponse({"unavailable": True, "reason": "only-eu"}, status_code=404)
    try:
        body, ctype, info = synthesize_eu(text)
    except Exception as exc:
        return JSONResponse({"unavailable": True, "reason": str(exc)[:200]}, status_code=503)
    return Response(
        content=body,
        media_type=ctype,
        headers={"X-Emap-Tts": info["engine"], "Cache-Control": "public, max-age=86400"},
    )


# Rate limiting por IP: ventana deslizante en memoria (sin Redis).
# 60 req/min es holgado para un usuario real y frena bots/escáneres.
_rate_window: dict[str, list[float]] = {}
_RATE_MAX = int(os.environ.get("EMAP_RATE_MAX", "60"))
_RATE_SECS = int(os.environ.get("EMAP_RATE_WINDOW", "60"))


def _rate_check(ip: str) -> bool:
    """True si la IP está bajo el límite."""
    now = time.monotonic()
    ts = _rate_window.setdefault(ip, [])
    cutoff = now - _RATE_SECS
    ts[:] = [t for t in ts if t > cutoff]
    if len(ts) >= _RATE_MAX:
        return False
    ts.append(now)
    return True


def _rerank(query: str, results: list[dict], k: int) -> list[dict]:
    """Re-ordena resultados con cross-encoder multilingüe. El reranker recibe
    (query, texto_del_poi) y devuelve scores; nos quedamos con los top-k.
    El texto del POI: nombre en ambos idiomas + tags (lo más representativo)."""
    if not results or _reranker is None:
        return results[:k]
    docs = []
    for r in results:
        name = r["name"] if isinstance(r["name"], str) else r["name"].get("es", "")
        docs.append(name)
    scores = list(_reranker.rerank(query, docs))
    scored = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:k]]


def _log_query(q: str, anchor: dict | None, results: list[dict]) -> None:
    """Log anónimo de cada búsqueda. Sin IP, sin sesión, coordenadas
    generalizadas a ~100m. Escritura no bloqueante: fallo no afecta respuesta."""
    try:
        gen_lat = round(anchor["lat"], 2) if anchor else None
        gen_lon = round(anchor["lon"], 2) if anchor else None
        entry = {
            "ts": int(time.time()),
            "date": date.today().isoformat(),
            "q": q[:200],
            "gen_lat": gen_lat,
            "gen_lon": gen_lon,
            "n_results": len(results),
            "layers": [r["layer"] for r in results[:5]],
            "retriever": _retriever.name if _retriever else "uninitialized",
        }
        log_dir = Path(os.environ.get("EMAP_QUERY_LOG", "/opt/emap-labs/data/queries"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{date.today().isoformat()}.jsonl"
        with log_file.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging nunca rompe la respuesta


@app.get("/search")
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    lat: float | None = None,
    lon: float | None = None,
    k: int = Query(default=5, ge=1, le=20),
):
    ip = request.client.host if request.client else "unknown"
    if not _rate_check(ip):
        return JSONResponse(status_code=429, content={
            "error": "rate_limit_exceeded",
            "retry_after_secs": _RATE_SECS,
            "limit": _RATE_MAX,
        })
    t0 = time.monotonic()
    anchor = {"lat": lat, "lon": lon} if lat is not None and lon is not None else None

    # Detección de categoría con scores para explicabilidad
    detected_layers, cat_scores, method = _retriever.detect_layers_with_scores(q)
    threshold = getattr(_retriever, "sim_threshold", 0.50)

    # Recuperar más candidatos de los necesarios para que el reranker elija.
    candidates = _retriever.retrieve(q, anchor, k=min(k * 4, 20))
    results = _rerank(q, candidates, k)

    out = []
    for r in results:
        item = {"id": r["id"], "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                "layer": r["layer"], "tags": r.get("tags") or {}}
        if anchor:
            item["distance_m"] = round(haversine_m(lat, lon, r["lat"], r["lon"]))
        item["why"] = explain_result(r, q, anchor, cat_scores, threshold)
        item["data"] = poi_freshness(r)
        out.append(item)

    _log_query(q, anchor, out)

    return {
        "query": q,
        "abstained": not out,  # no inventamos: sin categoría clara, vacío
        "results": out,
        "explanation": explain_detection(detected_layers, cat_scores, threshold, method),
        "retriever": f"{_retriever.name}+rerank",
        "reranked": len(candidates) > k,
        "took_ms": round((time.monotonic() - t0) * 1000),
        "attribution": "© OpenStreetMap contributors (ODbL) · Open Data Euskadi",
    }


@app.get("/hike-plan")
def hike_plan(peak: str, from_lat: float, from_lon: float,
              date: str | None = None, start_time: str = "08:00"):
    """Planifica una excursión al monte en transporte público.

    Args:
        peak: nombre de la cima (ES o EU)
        from_lat, from_lon: punto de origen
        date: fecha ISO (default: hoy)
        start_time: hora de salida HH:MM (default: 08:00)
    """
    return plan_hike(peak, from_lat, from_lon, date, start_time)


@app.get("/accessible-route")
def accessible_route(from_lat: float, from_lon: float,
                     to_lat: float, to_lon: float,
                     profile: str = "wheelchair"):
    """Calcula una ruta accesible.

    Perfiles: wheelchair, stroller, reduced_mobility.
    Devuelve distancia, duración, pasos y evaluación de accesibilidad.
    """
    return plan_accessible_route(from_lat, from_lon, to_lat, to_lon, profile)


@app.get("/accessible-pois")
def accessible_pois(lat: float, lon: float, radius: int = 1000,
                    poi_type: str = "toilets"):
    """Busca POIs accesibles cercanos vía Overpass.

    poi_type: toilets, elevator, pharmacy.
    Radio en metros (default 1000).
    """
    import math
    # Convertir radio en grados aprox
    dlat = radius / 111000
    dlon = radius / (111000 * math.cos(math.radians(lat)))
    bbox = (lat - dlat, lon - dlon, lat + dlat, lon + dlon)
    return {"pois": find_accessible_pois(bbox, poi_type), "count": 0}


@app.get("/isochrone")
def isochrone(lat: float, lon: float, minutes: int = 15,
              profile: str = "car", include_pois: bool = True):
    """Calcula isócrona: área alcanzable en X minutos.

    Perfiles: car, foot, bike.
    Si include_pois=true, incluye infraestructura alcanzable.
    """
    if include_pois:
        return find_pois_in_isochrone(lat, lon, minutes, profile)
    return compute_isochrone(lat, lon, minutes, profile)


@app.get("/data-quality")
def data_quality():
    """Informe de frescura y calidad de todas las capas de datos.

    Devuelve score global, conteo por estado (fresh/ok/stale/missing)
    y detalle por capa: fuente, licencia, edad del dato, SLA.
    """
    return quality_report()


@app.get("/poi-freshness")
def poi_freshness_endpoint(layer: str):
    """Frescura de datos para una capa específica."""
    return poi_freshness({"layer": layer})


RAIL = ("metro", "euskotren", "cercanias")
BUS = ("bilbobus", "bizkaibus")
KIND_RANK = {"neighborhood": 0, "district": 1, "municipality": 2}

# Índices espaciales por grupo de capas (KD-tree sobre lat/lon en radianes).
# Se construyen una vez al arranquear; las consultas son O(log n) vs O(n) del
# barrido original.
_kd_indices: dict[str, tuple["scipy.spatial.cKDTree", list[dict], list[str]]] = {}


def _build_kd_index(layers: tuple[str, ...]):
    """Construye un KD-tree con los POIs de las capas indicadas."""
    import scipy.spatial
    points: list[list[float]] = []
    items: list[dict] = []
    src_layer: list[str] = []
    for layer in layers:
        for p in _datasets.get(layer, []):
            points.append([math.radians(p["lat"]), math.radians(p["lon"])])
            items.append(p)
            src_layer.append(layer)
    if not points:
        return None
    tree = scipy.spatial.cKDTree(np.array(points))
    return tree, items, src_layer


def _kd_nearest(group: str, lat: float, lon: float):
    """POI más cercano del grupo usando KD-tree (distancia euclídea en rad →
    haversine para el resultado final)."""
    if group not in _kd_indices:
        _kd_indices[group] = _build_kd_index(_GROUP_LAYERS[group])
    entry = _kd_indices[group]
    if entry is None:
        return None
    tree, items, src_layer = entry
    d_rad, idx = tree.query([math.radians(lat), math.radians(lon)])
    p = items[idx]
    return {"name": p["name"], "layer": src_layer[idx],
            "distance_m": round(haversine_m(lat, lon, p["lat"], p["lon"]))}


# Mapeo grupo lógico → capas (se resuelve en startup, después de cargar datos).
_GROUP_LAYERS: dict[str, tuple[str, ...]] = {}


def _nearest(layers: tuple[str, ...], lat: float, lon: float):
    """Fallback O(n) para grupos sin KD-tree (p.ej. capa suelta)."""
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
def explain(request: Request, lat: float, lon: float):
    """Hechos del entorno de un punto — descriptivo, sin juicios (ETICA-DATOS)."""
    ip = request.client.host if request.client else "unknown"
    if not _rate_check(ip):
        return JSONResponse(status_code=429, content={
            "error": "rate_limit_exceeded",
            "retry_after_secs": _RATE_SECS,
            "limit": _RATE_MAX,
        })
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
        "nearest_rail": _kd_nearest("rail", lat, lon),
        "nearest_bus": _kd_nearest("bus", lat, lon),
        "nearest_toilet": _kd_nearest("toilets", lat, lon),
        "counts_300m": counts,
        "attribution": "© OpenStreetMap contributors (ODbL) · Open Data Euskadi",
    }
