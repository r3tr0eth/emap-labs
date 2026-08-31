"""Frescura y confianza del dato.

Cada POI y capa debería decir:
- cuándo se actualizó por última vez
- fuente y licencia
- confianza/frescura del dato
- si puede estar obsoleto
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

from regions import load_territory, resolve_layer_path

DATA_DIR = Path(os.environ.get("EMAP_DATA_DIR", "/opt/emap-labs/data")).resolve()
TERRITORY = load_territory(os.environ.get("EMAP_TERRITORY", "euskadi"))

# SLA por tipo de dato (días antes de considerar obsoleto)
DEFAULT_SLA_DAYS = {
    "fountains": 365,       # infraestructura estable
    "toilets": 365,
    "parking": 180,
    "bikepark": 180,
    "defib": 90,            # DEA: mantenimiento crítico
    "beaches": 7,           # playas: temporada
    "pharmacy": 90,
    "library": 180,
    "sports": 180,
    "food": 90,             # restaurantes cambian
    "lodging": 180,
    "hostel": 180,
    "camping": 90,
    "nature": 365,
    "peaks": 365,           # cimas no cambian
    "ev": 90,               # puntos de carga cambian
    "cameras": 30,          # cámaras: verificación frecuente
    "metro": 365,
    "euskotren": 365,
    "cercanias": 365,
    "bilbobus": 180,
    "bizkaibus": 180,
}
DEFAULT_SLA_DAYS.update(TERRITORY.freshness_sla_days)


def check_layer_freshness(layer: str) -> dict:
    """Comprueba la frescura de una capa."""
    path = _layer_path(layer)
    if not path or not path.exists():
        return {
            "layer": layer,
            "status": "missing",
            "path": str(path) if path else None,
        }

    try:
        doc = json.loads(path.read_text())
    except Exception as e:
        return {
            "layer": layer,
            "status": "corrupt",
            "error": str(e),
        }

    # Extraer metadatos
    generated = (
        doc.get("generated")
        or doc.get("updated")
        or doc.get("last_updated")
        or doc.get("source_updated")
    )
    source = doc.get("source") or doc.get("source_id", "unknown")
    license_ = doc.get("license", "unknown")
    count = doc.get("count") or len(doc.get("pois", []))

    # Calcular edad
    age_days = None
    stale = None
    if generated:
        try:
            gen_date = datetime.fromisoformat(generated.replace("Z", "+00:00")).date()
            age_days = (date.today() - gen_date).days
            sla = DEFAULT_SLA_DAYS.get(layer, 180)
            stale = age_days > sla
        except Exception:
            pass

    # Determinar estado
    if age_days is None:
        status = "unknown_date"
    elif stale:
        status = "stale"
    elif age_days < 7:
        status = "fresh"
    else:
        status = "ok"

    return {
        "layer": layer,
        "status": status,
        "count": count,
        "source": source,
        "license": license_,
        "generated": generated,
        "age_days": age_days,
        "sla_days": DEFAULT_SLA_DAYS.get(layer, 180),
        "stale": stale,
    }


def _layer_path(layer: str) -> Path | None:
    """Resuelve ruta de una capa."""
    return resolve_layer_path(DATA_DIR, TERRITORY, layer)


def quality_report(layers: list[str] | None = None) -> dict:
    """Genera informe de calidad de todas las capas."""
    if layers is None:
        layers = sorted(DEFAULT_SLA_DAYS.keys())

    t0 = time.monotonic()
    report = []
    status_counts: dict[str, int] = {}

    for layer in layers:
        info = check_layer_freshness(layer)
        report.append(info)
        s = info.get("status", "?")
        status_counts[s] = status_counts.get(s, 0) + 1

    # Score global (0-100)
    total = len(report)
    fresh = status_counts.get("fresh", 0) + status_counts.get("ok", 0)
    score = round(fresh / total * 100, 1) if total else 0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "score": score,
        "total_layers": total,
        "status_counts": status_counts,
        "layers": report,
        "stale_layers": [r["layer"] for r in report if r.get("stale")],
        "took_ms": int((time.monotonic() - t0) * 1000),
    }


def quality_report_from_documents(
    documents: dict[str, dict],
    sla_by_layer: dict[str, int] | None = None,
    layers: list[str] | None = None,
) -> dict:
    """Informe de freshness para un pack territorial ya cargado en runtime.

    No consulta globals ni rutas implícitas: permite auditar Madrid/Euskadi
    desde la misma instancia que sirve las peticiones.
    """
    sla_by_layer = sla_by_layer or DEFAULT_SLA_DAYS
    selected = layers or sorted(documents)
    t0 = time.monotonic()
    report = []
    status_counts: dict[str, int] = {}
    for layer in selected:
        doc = documents.get(layer)
        info = freshness_from_document(
            layer,
            doc or {},
            sla_days=sla_by_layer.get(layer) or DEFAULT_SLA_DAYS.get(layer, 180),
        ) if doc else {"layer": layer, "status": "unknown", "stale": None}
        report.append(info)
        status = info.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    fresh = status_counts.get("fresh", 0)
    total = len(report)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "score": round(fresh / total * 100, 1) if total else 0,
        "total_layers": total,
        "status_counts": status_counts,
        "layers": report,
        "stale_layers": [r["layer"] for r in report if r.get("stale")],
        "took_ms": int((time.monotonic() - t0) * 1000),
    }


def poi_freshness(
    poi: dict,
    *,
    document: dict | None = None,
    sla_days: int | None = None,
) -> dict:
    """Devuelve metadatos de frescura para un POI individual."""
    layer = poi.get("layer", poi.get("layer_id", ""))
    if document is None:
        info = check_layer_freshness(layer)
    else:
        info = freshness_from_document(
            layer,
            document,
            sla_days=sla_days if sla_days is not None else DEFAULT_SLA_DAYS.get(layer, 180),
        )

    return {
        "layer": layer,
        "data_source": info.get("source"),
        "license": info.get("license"),
        "data_generated": info.get("generated"),
        "retrieved_at": (document or {}).get("ingested_at"),
        "data_age_days": info.get("age_days"),
        "freshness": info.get("status"),
        "confidence": _confidence_label(info),
    }


def freshness_from_document(
    layer: str,
    document: dict,
    *,
    sla_days: int,
) -> dict:
    """Calcula freshness desde source_updated, sin estado territorial global."""
    source_updated = document.get("source_updated")
    age_days = None
    stale = None
    if source_updated:
        try:
            updated_date = datetime.fromisoformat(
                str(source_updated).replace("Z", "+00:00")
            ).date()
            age_days = (date.today() - updated_date).days
            stale = age_days > sla_days
        except (TypeError, ValueError):
            pass
    status = "unknown" if age_days is None else ("stale" if stale else "fresh")
    return {
        "layer": layer,
        "status": status,
        "count": document.get("count") or len(document.get("pois", [])),
        "source": document.get("source") or document.get("source_id", "unknown"),
        "license": document.get("license", "unknown"),
        "generated": source_updated,
        "age_days": age_days,
        "sla_days": sla_days,
        "stale": stale,
    }


def _confidence_label(info: dict) -> str:
    """Etiqueta de confianza legible."""
    status = info.get("status")
    if status == "fresh":
        return "high"
    if status == "ok":
        return "medium"
    if status == "stale":
        return "low"
    return "unknown"
