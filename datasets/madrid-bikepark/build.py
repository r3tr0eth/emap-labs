#!/usr/bin/env python3
"""Aparcabicis municipales de Madrid -> POIs EMAP normalizados."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from emap_geo import utm30n_to_wgs84


SOURCE_ID = "madrid_bikepark_official"
SOURCE_NAME = "Aparcabicis municipales de Madrid"
SOURCE_URL = (
    "https://datos.madrid.es/dataset/205099-0-aparca-bicis/resource/"
    "205099-3-aparca-bicis/download/205099_20260828_054402.json"
)
CKAN_PACKAGE_URL = (
    "https://datos.madrid.es/api/3/action/package_show?"
    "" + urllib.parse.urlencode({"id": "205099-0-aparca-bicis"})
)
ATTRIBUTION = "Ayuntamiento de Madrid (CC BY 4.0)"
MADRID_BBOX = (-3.90, 40.30, -3.50, 40.65)
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    ROOT.parent / "emap-next" / "data" / "processed" / "madrid" / "pois" / "bikepark.json"
)


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _in_madrid(lat: float, lon: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = MADRID_BBOX
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def _coordinates(record: dict[str, Any]) -> tuple[float, float, str] | None:
    lat = _number(record.get("LATITUD"))
    lon = _number(record.get("LONGITUD"))
    if lat is not None and lon is not None and _in_madrid(lat, lon):
        return lat, lon, "published_wgs84"
    easting = _number(record.get("COORD_GIS_X"))
    northing = _number(record.get("COORD_GIS_Y"))
    if easting is None or northing is None:
        return None
    lat, lon = utm30n_to_wgs84(easting, northing)
    if not _in_madrid(lat, lon):
        return None
    return lat, lon, "derived_etrs89_utm30n"


def _status(raw: Any) -> tuple[str, bool]:
    value = _text(raw).casefold()
    if value == "operativo":
        return "operational", True
    if value:
        return "out_of_service", False
    return "unknown", False


def _installed_on(value: Any) -> str | None:
    milliseconds = _number(value)
    if milliseconds is None or milliseconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(
            milliseconds / 1000, tz=timezone.utc
        ).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _address(record: dict[str, Any]) -> str:
    street = " ".join(
        part
        for part in (
            _text(record.get("TIPO_VIA")).title(),
            _text(record.get("NOM_VIA")).title(),
            _text(record.get("NUM_VIA")),
        )
        if part
    )
    auxiliary = _text(record.get("DIRECCION_AUX"))
    if auxiliary and street and auxiliary.casefold() not in street.casefold():
        return f"{auxiliary} · {street}"
    return auxiliary or street


def normalise_record(record: dict[str, Any]) -> dict[str, Any] | None:
    official_id = _text(record.get("ID"))
    coordinates = _coordinates(record)
    if not official_id or coordinates is None:
        return None
    lat, lon, coordinate_source = coordinates
    status, operational = _status(record.get("ESTADO"))
    tags: dict[str, Any] = {
        "official_id": official_id,
        "operational": operational,
        "status": status,
        "status_source": _text(record.get("ESTADO")) or "unknown",
        "coordinate_source": coordinate_source,
    }
    optional_tags = {
        "classification": _text(record.get("DESC_CLASIFICACION")),
        "district": _text(record.get("DISTRITO")).title(),
        "district_code": _text(record.get("COD_DISTRITO")),
        "neighborhood": _text(record.get("BARRIO")).title(),
        "neighborhood_code": _text(record.get("COD_BARRIO")),
        "postal_code": _text(record.get("COD_POSTAL")),
        "installed_on": _installed_on(record.get("FECHA_INSTALACION")),
        "load_date": _text(record.get("FX_CARGA")),
        "contract_code": _text(record.get("CONTRATO_COD")),
        "model": _text(record.get("MODELO")),
        "internal_code": _text(record.get("CODIGO_INTERNO")),
    }
    tags.update({key: value for key, value in optional_tags.items() if value})
    address = _address(record)
    poi: dict[str, Any] = {
        "id": f"bikepark:{official_id}",
        "name": {"es": f"Aparcabicis · {_text(record.get('NOM_VIA')) or official_id}"},
        "lat": round(lat, 7),
        "lon": round(lon, 7),
        "category": "bike_parking",
        "layer_id": "bikepark",
        "source_id": SOURCE_ID,
        "territory": "madrid",
        "tags": tags,
    }
    if address:
        poi["address"] = address
    return poi


def build_document(
    raw: bytes,
    *,
    source_updated: str,
    ingested_at: str,
    source_url: str = SOURCE_URL,
) -> dict[str, Any]:
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError("la fuente oficial debe ser una lista JSON")
    by_id: dict[str, dict[str, Any]] = {}
    discard_reasons: Counter[str] = Counter()
    for record in records:
        if not isinstance(record, dict):
            discard_reasons["invalid_record"] += 1
            continue
        official_id = _text(record.get("ID"))
        if not official_id:
            discard_reasons["missing_id"] += 1
            continue
        poi = normalise_record(record)
        if poi is None:
            discard_reasons["invalid_coordinates"] += 1
            continue
        if poi["id"] in by_id:
            discard_reasons["duplicate_id"] += 1
            continue
        by_id[poi["id"]] = poi
    pois = sorted(by_id.values(), key=lambda poi: poi["id"])
    coordinate_counts = Counter(
        poi["tags"]["coordinate_source"] for poi in pois
    )
    source_records = len(records)
    discarded_records = sum(discard_reasons.values())
    reused_stages = [
        "geo_normalization",
        "common_poi_schema",
        "territorial_pack",
        "core_retrieval_evidence",
    ]
    return {
        "version": "1.0.0",
        "territory": "madrid",
        "layer_id": "bikepark",
        "source_id": SOURCE_ID,
        "source": SOURCE_NAME,
        "source_url": source_url,
        "source_updated": source_updated,
        "ingested_at": ingested_at,
        "generated": source_updated,
        "freshness_sla_days": 2,
        "license": "CC-BY-4.0",
        "attribution": ATTRIBUTION,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_records": source_records,
        "accepted_records": len(pois),
        "discarded_records": discarded_records,
        "discard_reasons": dict(sorted(discard_reasons.items())),
        "coordinate_counts": dict(sorted(coordinate_counts.items())),
        "count": len(pois),
        "dropped": discarded_records,
        "schema_id": "https://emap.eus/schemas/poi.schema.json",
        "schema_reused": True,
        "territorial_reuse_ratio": round(len(reused_stages) / 6, 3),
        "territorial_reuse": {
            "formula": "reused_stages / 6",
            "reused_stages": reused_stages,
            "specific_stages": ["source_acquisition", "source_format_adapter"],
        },
        "territorial_specific_code": ["datasets/madrid-bikepark/build.py"],
        "coverage": {
            "territory": "Municipio de Madrid",
            "bbox": list(MADRID_BBOX),
            "notes": (
                "Solo aparcabicis municipales situados en vía pública; no incluye "
                "instalaciones interiores ni parques históricos o forestales."
            ),
        },
        "quality": {
            "records": len(pois),
            "source_records": source_records,
            "dropped": discarded_records,
            "discard_reasons": dict(sorted(discard_reasons.items())),
            "unique_ids": len(by_id),
            "coordinate_counts": dict(sorted(coordinate_counts.items())),
        },
        "pois": pois,
    }


def fetch_source() -> tuple[bytes, str, str, str]:
    request = urllib.request.Request(
        CKAN_PACKAGE_URL,
        headers={"Accept": "application/json", "User-Agent": "emap-labs/0.1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        package = json.loads(response.read())
    resources = package.get("result", {}).get("resources", [])
    resource = next(
        item for item in resources
        if item.get("id") == "205099-3-aparca-bicis"
    )
    source_url = str(resource["url"])
    modified = resource.get("last_modified") or resource.get("modified")
    if not modified:
        raise ValueError("el recurso oficial no tiene fecha de modificación")
    source_updated = str(modified)[:10]
    with urllib.request.urlopen(
        urllib.request.Request(source_url, headers={"User-Agent": "emap-labs/0.1"}),
        timeout=60,
    ) as response:
        raw = response.read()
    ingested_at = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    return raw, source_updated, ingested_at, source_url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--source-updated")
    parser.add_argument("--ingested-at")
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.input:
        if not args.source_updated or not args.ingested_at:
            parser.error("--source-updated y --ingested-at son obligatorios con --input")
        raw, source_updated, ingested_at, source_url = (
            args.input.read_bytes(), args.source_updated, args.ingested_at, args.source_url
        )
    else:
        if args.source_updated or args.ingested_at:
            parser.error("las fechas manuales solo se aceptan junto con --input")
        raw, source_updated, ingested_at, source_url = fetch_source()
    datetime.strptime(source_updated, "%Y-%m-%d")
    datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
    document = build_document(
        raw,
        source_updated=source_updated,
        ingested_at=ingested_at,
        source_url=source_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"{args.output}: {document['accepted_records']}/{document['source_records']} "
        f"aceptados; {document['discarded_records']} descartados"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
