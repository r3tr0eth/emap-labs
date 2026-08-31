#!/usr/bin/env python3
"""Aparcamientos municipales de Madrid -> POIs EMAP normalizados."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from emap_geo import utm30n_to_wgs84


SOURCE_ID = "madrid_parking_official"
SOURCE_NAME = "Aparcamientos públicos municipales de Madrid"
SOURCE_URL = (
    "https://datos.madrid.es/dataset/202625-0-aparcamientos-publicos/"
    "resource/202625-3-aparcamientos-publicos-csv/download/"
    "202625-0-aparcamientos-publicos.csv"
)
ATTRIBUTION = "Ayuntamiento de Madrid (CC BY 4.0)"
MADRID_BBOX = (-3.90, 40.30, -3.50, 40.65)
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    ROOT.parent / "emap-next" / "data" / "processed" / "madrid" / "pois" / "parking.json"
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
    easting = _number(record.get("COORDENADA-X"))
    northing = _number(record.get("COORDENADA-Y"))
    if easting is None or northing is None:
        return None
    lat, lon = utm30n_to_wgs84(easting, northing)
    if not _in_madrid(lat, lon):
        return None
    return lat, lon, "derived_etrs89_utm30n"


def _address(record: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            _text(record.get("CLASE-VIAL")).title(),
            _text(record.get("NOMBRE-VIA")).title(),
            _text(record.get("NUM")),
        )
        if part
    )


def _access_scope(raw_type: Any) -> str:
    value = _text(raw_type).casefold()
    if value.endswith("aparcamientospublicos"):
        return "public"
    if value.endswith("aparcamientosresidentes"):
        return "resident_or_mixed"
    return "unknown"


def normalise_record(record: dict[str, Any]) -> dict[str, Any] | None:
    official_id = _text(record.get("PK"))
    coordinates = _coordinates(record)
    if not official_id or coordinates is None:
        return None
    lat, lon, coordinate_source = coordinates
    name = _text(record.get("NOMBRE")) or f"Aparcamiento {official_id}"
    address = _address(record)
    tags = {
        "official_id": official_id,
        "coordinate_source": coordinate_source,
        "access_scope": _access_scope(record.get("TIPO")),
    }
    optional_tags = {
        "opening_hours_text": _text(record.get("HORARIO")),
        "description": _text(record.get("DESCRIPCION")),
        "accessibility_code": _text(record.get("ACCESIBILIDAD")),
        "official_url": _text(record.get("CONTENT-URL")),
        "district": _text(record.get("DISTRITO")).title(),
        "district_code": _text(record.get("COD-DISTRITO")),
        "neighborhood": _text(record.get("BARRIO")).title(),
        "neighborhood_code": _text(record.get("COD-BARRIO")),
        "postal_code": _text(record.get("CODIGO-POSTAL")),
        "source_type": _text(record.get("TIPO")),
    }
    tags.update({key: value for key, value in optional_tags.items() if value})
    poi: dict[str, Any] = {
        "id": f"parking:{official_id}",
        "name": {"es": name},
        "lat": round(lat, 7),
        "lon": round(lon, 7),
        "category": "parking",
        "layer_id": "parking",
        "source_id": SOURCE_ID,
        "territory": "madrid",
        "tags": tags,
    }
    if address:
        poi["address"] = address
    return poi


def parse_records(raw: bytes) -> list[dict[str, str]]:
    """Lee el CSV municipal, cuyo recurso real se publica en ISO-8859-1."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("iso-8859-1")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames or "PK" not in reader.fieldnames:
        raise ValueError("CSV de aparcamientos sin cabecera PK")
    return [dict(record) for record in reader]


def build_document(
    raw: bytes,
    *,
    source_updated: str,
    ingested_at: str,
) -> dict[str, Any]:
    records = parse_records(raw)
    by_id: dict[str, dict[str, Any]] = {}
    discard_reasons: Counter[str] = Counter()
    for record in records:
        if not _text(record.get("PK")):
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
    specific_stages = ["source_acquisition", "source_format_adapter"]
    return {
        "version": "1.0.0",
        "territory": "madrid",
        "layer_id": "parking",
        "source_id": SOURCE_ID,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
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
            "specific_stages": specific_stages,
        },
        "territorial_specific_code": ["datasets/madrid-parking/build.py"],
        "coverage": {
            "territory": "Municipio de Madrid",
            "bbox": list(MADRID_BBOX),
            "notes": (
                "Inventario municipal oficial. La tipología distingue entradas "
                "públicas de residentes o mixtas; no contiene ocupación realtime."
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


def fetch_source() -> tuple[bytes, str, str]:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "Accept": "text/csv",
            "User-Agent": "emap-labs/0.1 (+https://github.com/r3tr0eth/emap-labs)",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        modified = response.headers.get("Last-Modified")
    if not modified:
        raise ValueError("la fuente oficial no devolvió Last-Modified")
    source_updated = parsedate_to_datetime(modified).date().isoformat()
    ingested_at = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    return raw, source_updated, ingested_at


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="snapshot CSV oficial local")
    parser.add_argument("--source-updated")
    parser.add_argument("--ingested-at")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.input:
        if not args.source_updated or not args.ingested_at:
            parser.error(
                "--source-updated y --ingested-at son obligatorios con --input"
            )
        raw = args.input.read_bytes()
        source_updated = args.source_updated
        ingested_at = args.ingested_at
    else:
        if args.source_updated or args.ingested_at:
            parser.error("las fechas manuales solo se aceptan junto con --input")
        raw, source_updated, ingested_at = fetch_source()
    datetime.strptime(source_updated, "%Y-%m-%d")
    datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
    document = build_document(
        raw, source_updated=source_updated, ingested_at=ingested_at
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
