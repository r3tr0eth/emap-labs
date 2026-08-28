#!/usr/bin/env python3
"""Fuentes de beber del Ayuntamiento de Madrid -> POIs EMAP normalizados.

La fuente publica latitud/longitud en la mayoría de registros y coordenadas
ETRS89 / UTM 30N en todos. El adapter usa las coordenadas publicadas cuando
son válidas y recupera los registros restantes mediante la primitiva geo
compartida con Euskadi.

Uso reproducible con un snapshot local::

    ../emap-next/.venv/bin/python datasets/madrid-fountains/build.py \
      --input /ruta/300051-0-fuentes.json --source-updated 2026-08-28

Sin ``--input`` descarga el recurso oficial y obtiene ``source_updated`` de
la cabecera HTTP Last-Modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from emap_geo import utm30n_to_wgs84


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    ROOT.parent
    / "emap-next"
    / "data"
    / "processed"
    / "madrid"
    / "pois"
    / "fountains.json"
)
SOURCE_URL = (
    "https://datos.madrid.es/dataset/300051-0-fuentes/resource/"
    "300051-0-fuentes/download/300051-0-fuentes.json"
)
SOURCE_ID = "madrid_fountains_official"
SOURCE_NAME = "Fuentes de beber del Ayuntamiento de Madrid"
ATTRIBUTION = "Ayuntamiento de Madrid (CC BY 4.0)"
MADRID_BBOX = (-3.90, 40.30, -3.50, 40.65)  # min_lon, min_lat, max_lon, max_lat

STATUS_MAP = {
    "OPERATIVO": ("operational", True),
    "FUERA_DE_SERVICIO": ("out_of_service", False),
    "NO_OPERATIVO": ("out_of_service", False),
    "CERRADA_TEMPORALMENTE": ("temporarily_closed", False),
    # La exportación real de 2026-08 trunca este literal a 20 caracteres.
    "CERRADA_TEMPORALMENT": ("temporarily_closed", False),
    "NO_PREPARADO": ("not_ready", False),
}


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


def _normalised_status(raw: Any) -> tuple[str, bool]:
    text = unicodedata.normalize("NFD", _text(raw).upper())
    key = "".join(char for char in text if unicodedata.category(char) != "Mn")
    key = key.replace(" ", "_")
    return STATUS_MAP.get(key, ("unknown", False))


def _address(record: dict[str, Any]) -> str:
    auxiliary = _text(record.get("DIRECCION_AUX"))
    street = " ".join(
        part
        for part in (
            _text(record.get("TIPO_VIA")).title(),
            _text(record.get("NOM_VIA")).title(),
            _text(record.get("NUM_VIA")),
        )
        if part
    )
    if auxiliary and street and auxiliary.casefold() not in street.casefold():
        return f"{auxiliary} · {street}"
    return auxiliary or street


def _installed_on(value: Any) -> str | None:
    milliseconds = _number(value)
    if milliseconds is None or milliseconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def normalise_record(record: dict[str, Any]) -> dict[str, Any] | None:
    official_id = _text(record.get("ID"))
    coordinates = _coordinates(record)
    if not official_id or coordinates is None:
        return None

    lat, lon, coordinate_source = coordinates
    address = _address(record)
    district = _text(record.get("DISTRITO")).title()
    place = address or district or official_id
    status, operational = _normalised_status(record.get("ESTADO"))

    tags: dict[str, Any] = {
        "official_id": official_id,
        "operational": operational,
        "status": status,
        "status_source": _text(record.get("ESTADO")) or "unknown",
        "coordinate_source": coordinate_source,
    }
    optional_tags = {
        "district": district,
        "district_code": _text(record.get("COD_DISTRITO")),
        "neighborhood": _text(record.get("BARRIO")).title(),
        "neighborhood_code": _text(record.get("COD_BARRIO")),
        "postal_code": _text(record.get("COD_POSTAL")),
        "location_type": _text(record.get("UBICACION")),
        "use": _text(record.get("USO")).lower(),
        "model": _text(record.get("MODELO")),
        "installed_on": _installed_on(record.get("FECHA_INSTALACION")),
    }
    tags.update({key: value for key, value in optional_tags.items() if value})

    poi: dict[str, Any] = {
        "id": f"fountains:{official_id}",
        "name": {"es": f"Fuente de agua · {place}"},
        "lat": round(lat, 7),
        "lon": round(lon, 7),
        "category": "fountain",
        "layer_id": "fountains",
        "source_id": SOURCE_ID,
        "territory": "madrid",
        "tags": tags,
    }
    if address:
        poi["address"] = address
    return poi


def build_document(raw: bytes, source_updated: str) -> dict[str, Any]:
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError("la fuente oficial debe ser una lista JSON")

    by_id: dict[str, dict[str, Any]] = {}
    dropped = 0
    for record in records:
        if not isinstance(record, dict):
            dropped += 1
            continue
        poi = normalise_record(record)
        if poi is None:
            dropped += 1
            continue
        if poi["id"] in by_id:
            dropped += 1
            continue
        by_id[poi["id"]] = poi

    pois = sorted(by_id.values(), key=lambda poi: poi["id"])
    status_counts = Counter(poi["tags"]["status"] for poi in pois)
    coordinate_counts = Counter(poi["tags"]["coordinate_source"] for poi in pois)
    return {
        "version": "1.0.0",
        "territory": "madrid",
        "layer_id": "fountains",
        "source_id": SOURCE_ID,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "source_updated": source_updated,
        "generated": source_updated,
        "license": "CC-BY-4.0",
        "attribution": ATTRIBUTION,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "count": len(pois),
        "dropped": dropped,
        "status_counts": dict(sorted(status_counts.items())),
        "coordinate_counts": dict(sorted(coordinate_counts.items())),
        "coverage": {
            "territory": "Municipio de Madrid",
            "bbox": list(MADRID_BBOX),
            "notes": (
                "Inventario municipal oficial; cobertura limitada al municipio. "
                "No se estima completeness sin un universo independiente."
            ),
        },
        "quality": {
            "records": len(pois),
            "dropped": dropped,
            "unique_ids": len(by_id),
            "status_counts": dict(sorted(status_counts.items())),
            "coordinate_counts": dict(sorted(coordinate_counts.items())),
        },
        "pois": pois,
    }


def fetch_source() -> tuple[bytes, str]:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "emap-labs/0.1 (+https://github.com/r3tr0eth/emap-labs)",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        modified = response.headers.get("Last-Modified")
    if not modified:
        raise ValueError("la fuente oficial no devolvió Last-Modified")
    source_updated = parsedate_to_datetime(modified).date().isoformat()
    return raw, source_updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="snapshot JSON oficial local")
    parser.add_argument(
        "--source-updated",
        help="fecha YYYY-MM-DD obligatoria con --input; evita frescura inventada",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.input:
        if not args.source_updated:
            parser.error("--source-updated es obligatorio cuando se usa --input")
        raw = args.input.read_bytes()
        source_updated = args.source_updated
    else:
        if args.source_updated:
            parser.error("--source-updated solo se acepta junto con --input")
        raw, source_updated = fetch_source()

    # Valida también fechas proporcionadas manualmente.
    datetime.strptime(source_updated, "%Y-%m-%d")
    document = build_document(raw, source_updated)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"{args.output}: {document['count']} POIs, "
        f"{document['dropped']} descartados, fuente {source_updated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
