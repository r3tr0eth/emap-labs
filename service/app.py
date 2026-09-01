"""emap-labs semantic service — el retriever híbrido como servicio HTTP.

Corre en el VPS (patrón OTP): emap-next (Vercel) hace proxy vía
EMAP_SEMANTIC_URL. Sin base de datos: descriptores de categoría en memoria
+ búsqueda estructurada sobre las capas del pack territorial cargado.

    EMAP_DATA_DIR=/opt/emap-labs/data uvicorn app:app --port 8083

Validación y configuración reproducible: evals/ y regions/<id>/region.yaml.
"""
from __future__ import annotations

import json
import math
import os
import hashlib
import sys
import threading
import time
from datetime import date
from pathlib import Path

import numpy as np

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response

LABS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LABS_ROOT))
sys.path.insert(0, str(LABS_ROOT / "evals"))
from regions import list_territories, load_territory  # noqa: E402
from service.runtime import (  # noqa: E402
    RuntimeRegistry,
    TerritoryResolutionError,
)

from semantic_local import HybridRetriever, HybridRetrieverFactory  # noqa: E402

try:
    from emap_geo.distance import haversine_m  # noqa: E402
except ImportError:  # CI / entorno sin emap-next al lado: fallback vendorizado
    from _geo import haversine_m  # noqa: E402
from explain import explain_detection, explain_result  # noqa: E402
from hike_planner import plan_hike  # noqa: E402
from accessibility import plan_accessible_route, find_accessible_pois  # noqa: E402
from isochrones import compute_isochrone, find_pois_in_isochrone  # noqa: E402
from data_freshness import BASE_SLA_DAYS, quality_report, quality_report_from_documents, poi_freshness, freshness_from_document  # noqa: E402
from response_contract import SCHEMA_VERSION, build_response  # noqa: E402

DATA_DIR = Path(os.environ.get("EMAP_DATA_DIR", "../emap-next/data")).resolve()
TERRITORY = load_territory("euskadi")  # compatibilidad temporal de /explain

app = FastAPI(title="emap-labs semantic", version="0.2")
_retriever: HybridRetriever | None = None
_counts: dict[str, int] = {}
_datasets: dict[str, list[dict]] = {}
_units: list[dict] = []  # barrios/distritos/municipios con anillos (lat,lon)
_retriever_factory = HybridRetrieverFactory()
_METRICS = {"request_count": 0, "success": 0, "no_result": 0,
            "abstained": 0, "unsupported": 0, "errors": 0,
            "source_failure": 0, "stale_source": 0, "model_profile": "minilm",
            "by_territory": {}, "by_retriever": {}, "latency_ms_total": 0}
_METRICS_LOCK = threading.Lock()


def _ensure_poi_id(poi: dict, layer: str, idx: int) -> dict:
    """Los POIs de euskadi-places no traen id: genera uno estable (<layer>:<idx>)
    para que el retriever y /search funcionen uniformemente."""
    if "id" not in poi:
        poi["id"] = f"{layer}:{idx}"
    return poi


@app.on_event("startup")
def load() -> None:
    global _retriever
    _METRICS["model_profile"] = os.environ.get("EMAP_RETRIEVER_PROFILE", "e5large")
    configured = os.environ.get("EMAP_TERRITORIES")
    territory_ids = tuple(
        territory_id.strip()
        for territory_id in configured.split(",")
        if territory_id.strip()
    ) if configured else tuple(list_territories(runnable_only=True))
    registry = RuntimeRegistry.build(
        data_root=DATA_DIR,
        territory_ids=territory_ids,
        retriever_factory=_retriever_factory,
    )
    app.state.runtime_registry = registry

    # Compatibilidad de endpoints aún Euskadi-only; /search ya no usa estos
    # aliases y nunca resuelve silenciosamente al territorio vasco.
    legacy = registry.resolve(territory_id="euskadi")
    datasets = dict(legacy.datasets)
    _retriever = legacy.retriever
    _retriever.set_anchor_names([])
    _counts.clear()
    _counts.update(legacy.counts)
    _datasets.clear()
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
    print(f"semantic listo: {sum(_counts.values())} POIs en {len(_counts)} capas, "
          f"{len(_units)} unidades administrativas")


@app.get("/healthz")
def healthz():
    registry = getattr(app.state, "runtime_registry", None)
    if registry is None:
        return {"ok": False, "error": "runtime_uninitialized", "territories": {}}
    territories = registry.health()
    return {
        "ok": all(info["ok"] for info in territories.values()),
        "territories": territories,
        "territories_served": sorted(territories),
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


def _log_query(
    q: str, anchor: dict | None, results: list[dict], retriever_name: str
) -> None:
    """Log anónimo de cada búsqueda. Sin IP, sesión, texto ni coordenadas.
    Escritura no bloqueante: fallo no afecta respuesta."""
    try:
        entry = {
            "ts": int(time.time()),
            "date": date.today().isoformat(),
            "q_sha256": hashlib.sha256(q.encode("utf-8")).hexdigest()[:16],
            "n_results": len(results),
            "layers": [r["layer"] for r in results[:5]],
            "retriever": retriever_name,
        }
        log_dir = Path(os.environ.get("EMAP_QUERY_LOG", "/opt/emap-labs/data/queries"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{date.today().isoformat()}.jsonl"
        with log_file.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging nunca rompe la respuesta


def _metric(territory: str, retriever: str, latency_ms: int,
            answer_status: str, stale_count: int = 0,
            source_failures: int = 0) -> None:
    """Contadores por answer_status del contrato: no_result (corpus sin
    match), abstained (detección bajo umbral) y unsupported (categoría no
    soportada) son señales distintas. source_failures cuenta resultados
    servidos sin documento de fuente (metadatos ausentes)."""
    with _METRICS_LOCK:
        _METRICS["request_count"] += 1
        _METRICS["success"] += 1
        _METRICS["latency_ms_total"] += latency_ms
        _METRICS["stale_source"] += stale_count
        _METRICS["source_failure"] += source_failures
        if answer_status == "NO_RESULT":
            _METRICS["no_result"] += 1
        elif answer_status == "ABSTAINED":
            _METRICS["abstained"] += 1
        elif answer_status == "UNSUPPORTED":
            _METRICS["unsupported"] += 1
        for bucket, key in (("by_territory", territory), ("by_retriever", retriever)):
            values = _METRICS[bucket]
            values[key] = values.get(key, 0) + 1


def _metric_error() -> None:
    """Cuenta fallos de entrada/servicio sin guardar payloads del usuario."""
    with _METRICS_LOCK:
        _METRICS["errors"] += 1


@app.get("/metrics")
def metrics():
    """Métricas agregadas; no expone texto ni coordenadas de usuarios."""
    with _METRICS_LOCK:
        out = dict(_METRICS)
        out["by_territory"] = dict(_METRICS["by_territory"])
        out["by_retriever"] = dict(_METRICS["by_retriever"])
    out["latency_ms_avg"] = round(
        out["latency_ms_total"] / out["request_count"], 2
    ) if out["request_count"] else 0
    return out


@app.get("/search")
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    territory: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    k: int = Query(default=5, ge=1, le=20),
):
    ip = request.client.host if request.client else "unknown"
    if not _rate_check(ip):
        _metric_error()
        return JSONResponse(status_code=429, content={
            "error": "rate_limit_exceeded",
            "schema_version": SCHEMA_VERSION,
            "answerable": False,
            "retry_after_secs": _RATE_SECS,
            "limit": _RATE_MAX,
        })
    t0 = time.monotonic()
    registry = getattr(request.app.state, "runtime_registry", None)
    if registry is None:
        _metric_error()
        return JSONResponse(
            status_code=503,
            content={"error": "runtime_uninitialized", "answerable": False,
                     "schema_version": SCHEMA_VERSION},
        )
    try:
        runtime = registry.resolve(territory_id=territory, lat=lat, lon=lon)
    except TerritoryResolutionError as exc:
        _metric_error()
        status_code = 404 if exc.code == "unknown_territory" else 422
        return JSONResponse(
            status_code=status_code,
            content={"error": exc.code, "detail": exc.detail, "answerable": False,
                     "schema_version": SCHEMA_VERSION},
        )
    anchor = {"lat": lat, "lon": lon} if lat is not None and lon is not None else None
    retriever = runtime.retriever

    # Detección de categoría con scores para explicabilidad
    detected_layers, cat_scores, method = retriever.detect_layers_with_scores(q)
    threshold = getattr(retriever, "sim_threshold", 0.50)

    results = retriever.retrieve(q, anchor, k=k)

    out = []
    missing_docs = 0
    for r in results:
        item = {"id": r["id"], "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                "layer": r["layer"], "tags": r.get("tags") or {}}
        if anchor:
            item["distance_m"] = round(haversine_m(lat, lon, r["lat"], r["lon"]))
        documents = runtime.documents or {}
        source_document = documents.get(r["layer"])
        if source_document is None:
            missing_docs += 1
        item["why"] = explain_result(
            r,
            q,
            anchor,
            cat_scores,
            threshold,
            source_document=source_document,
        )
        item["data"] = poi_freshness(
            r,
            document=source_document,
            # None → poi_freshness cae a BASE_SLA_DAYS por capa (nunca al SLA
            # de otro territorio, nunca a un 180 plano).
            sla_days=runtime.territory.freshness_sla_days.get(r["layer"]),
        )
        out.append(item)

    _log_query(q, anchor, out, retriever.name)
    response = build_response(
        query=q,
        runtime={"territory": runtime.territory.id, "territory_version": runtime.territory.version},
        results=out,
        detection=explain_detection(detected_layers, cat_scores, threshold, method),
        retriever=retriever.name,
        took_ms=round((time.monotonic() - t0) * 1000),
        attribution=runtime.territory.attribution,
    )
    _metric(runtime.territory.id, retriever.name, response["took_ms"],
            response["answer_status"],
            sum((r.get("data") or {}).get("freshness") == "stale" for r in out),
            missing_docs)
    return response


@app.get("/nearby")
def nearby(
    request: Request,
    layer: str,
    lat: float,
    lon: float,
    territory: str | None = None,
    k: int = Query(default=5, ge=1, le=20),
):
    """Nearby verificable sobre el pack territorial resuelto.

    Es la demo mínima de Core: no interpreta texto ni inventa disponibilidad;
    ordena entidades normalizadas por distancia y compone evidencia común.
    """
    registry = getattr(request.app.state, "runtime_registry", None)
    if registry is None:
        _metric_error()
        return JSONResponse(status_code=503, content={"error": "runtime_uninitialized", "answerable": False,
                     "schema_version": SCHEMA_VERSION})
    try:
        runtime = registry.resolve(territory_id=territory, lat=lat, lon=lon)
    except TerritoryResolutionError as exc:
        _metric_error()
        return JSONResponse(status_code=404 if exc.code == "unknown_territory" else 422,
                            content={"error": exc.code, "detail": exc.detail, "answerable": False,
                     "schema_version": SCHEMA_VERSION})
    if layer not in runtime.datasets:
        _metric_error()
        return JSONResponse(status_code=422, content={"error": "unsupported_layer", "layer": layer, "answerable": False,
                     "schema_version": SCHEMA_VERSION})
    t0 = time.monotonic()
    document = (runtime.documents or {}).get(layer)
    rows = sorted(runtime.datasets[layer], key=lambda p: haversine_m(lat, lon, p["lat"], p["lon"]))[:k]
    results = []
    for row in rows:
        item = {"id": row["id"], "name": row["name"], "lat": row["lat"], "lon": row["lon"],
                "layer": layer, "tags": row.get("tags") or {},
                "distance_m": round(haversine_m(lat, lon, row["lat"], row["lon"]))}
        explain_row = {**row, "layer": layer}
        item["why"] = explain_result(explain_row, f"nearby {layer}", {"lat": lat, "lon": lon}, {layer: 1.0}, 0.0, source_document=document)
        item["data"] = poi_freshness(row, document=document,
                                     sla_days=runtime.territory.freshness_sla_days.get(layer))
        results.append(item)
    response = build_response(
        query=f"nearby:{layer}",
        runtime={"territory": runtime.territory.id, "territory_version": runtime.territory.version},
        results=results,
        detection={"detected": layer, "method": "geo", "confidence": 1.0, "threshold": 0.0},
        retriever="geo-nearest",
        took_ms=round((time.monotonic() - t0) * 1000),
        attribution=runtime.territory.attribution,
    )
    _metric(runtime.territory.id, "geo-nearest", response["took_ms"],
            response["answer_status"],
            sum((r.get("data") or {}).get("freshness") == "stale" for r in results),
            len(results) if document is None else 0)
    return response


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
    pois = find_accessible_pois(bbox, poi_type)
    return {"pois": pois, "count": len(pois)}


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
def data_quality(territory: str | None = None):
    """Informe de frescura y calidad de todas las capas de datos.

    Devuelve score global, conteo por estado (fresh/ok/stale/missing)
    y detalle por capa: fuente, licencia, edad del dato, SLA.
    """
    if not territory:
        return quality_report()
    registry = getattr(app.state, "runtime_registry", None)
    try:
        runtime = registry.resolve(territory_id=territory) if registry else None
    except TerritoryResolutionError as exc:
        return JSONResponse(status_code=404 if exc.code == "unknown_territory" else 422,
                            content={"error": exc.code, "detail": exc.detail})
    if runtime is None:
        return JSONResponse(status_code=503, content={"error": "runtime_uninitialized"})
    return quality_report_from_documents(runtime.documents, runtime.territory.freshness_sla_days)


@app.get("/poi-freshness")
def poi_freshness_endpoint(layer: str, territory: str | None = None):
    """Frescura de datos para una capa específica."""
    if not territory:
        return poi_freshness({"layer": layer})
    registry = getattr(app.state, "runtime_registry", None)
    try:
        runtime = registry.resolve(territory_id=territory) if registry else None
    except TerritoryResolutionError as exc:
        return JSONResponse(status_code=404 if exc.code == "unknown_territory" else 422,
                            content={"error": exc.code, "detail": exc.detail})
    if runtime is None:
        return JSONResponse(status_code=503, content={"error": "runtime_uninitialized"})
    document = runtime.documents.get(layer)
    if document is None:
        return JSONResponse(status_code=404, content={"error": "unsupported_layer", "layer": layer})
    sla_days = runtime.territory.freshness_sla_days.get(layer)
    if sla_days is None:
        sla_days = BASE_SLA_DAYS.get(layer, 180)
    return freshness_from_document(layer, document, sla_days=sla_days)


RAIL = ("metro", "euskotren", "cercanias")
BUS = ("bilbobus", "bizkaibus")
KIND_RANK = {"neighborhood": 0, "district": 1, "municipality": 2}

# Índices espaciales por grupo de capas (KD-tree sobre lat/lon en radianes).
# Se construyen una vez al arranquear; las consultas son O(log n) vs O(n) del
# barrido original.
_kd_indices: dict[str, tuple[object, list[dict], list[str]] | None] = {}


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
        _metric_error()
        return JSONResponse(status_code=429, content={
            "error": "rate_limit_exceeded",
            "schema_version": SCHEMA_VERSION,
            "answerable": False,
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
