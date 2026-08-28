#!/usr/bin/env python3
"""Construye el artefacto de release de datasets de EMAP Labs.

Lee los datasets fuente de ../emap-next (solo lectura — NO los modifica),
calcula los 6 metadatos (fuente, licencia, fecha, checksum, cobertura,
calidad) y produce:

  releases/v<version>/manifest.json           metadatos + checksums (se commitea)
  dist/emap-labs-datasets-v<version>.tar.gz   datos + manifest + README (release asset)

Uso: python releases/build_release.py --version 0.3.0-rc.1
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import tarfile
from datetime import date
from pathlib import Path

LABS = Path(__file__).resolve().parent.parent
EMAP_NEXT = (LABS / ".." / "emap-next").resolve()
DIST = LABS / "dist"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")

# Procedencia curada a mano (verificada contra los generadores de emap-next).
# records_field: clave de la lista de registros en cada JSON.
DATASETS = [
    {
        "id": "dea-euskadi",
        "title": "Desfibriladores (DEA) de Euskadi",
        "src": "data/pois-euskadi/defib.json",
        "records_field": "pois",
        "source": "Registro Vasco de DEA — Dpto. de Salud, Gobierno Vasco",
        "license": "Open Data Euskadi (CC BY 4.0)",
        "coverage": {"territory": "euskadi", "notes": "Registro oficial; cobertura autonómica."},
    },
    {
        "id": "pois-euskadi-fountains",
        "title": "Fuentes de agua potable (Euskadi)",
        "src": "data/pois-euskadi/fountains.json",
        "records_field": "pois",
        "source": "OpenStreetMap (Overpass, amenity=drinking_water)",
        "license": "ODbL 1.0 © OpenStreetMap contributors",
        "coverage": {"territory": "euskadi", "notes": "Cobertura según densidad de mapeo en OSM."},
    },
    {
        "id": "pois-euskadi-toilets",
        "title": "Aseos públicos (Euskadi)",
        "src": "data/pois-euskadi/toilets.json",
        "records_field": "pois",
        "source": "OpenStreetMap (Overpass, amenity=toilets)",
        "license": "ODbL 1.0 © OpenStreetMap contributors",
        "coverage": {"territory": "euskadi", "notes": "Cobertura según densidad de mapeo en OSM."},
    },
    {
        "id": "pois-euskadi-parking",
        "title": "Aparcamientos (Euskadi)",
        "src": "data/pois-euskadi/parking.json",
        "records_field": "pois",
        "source": "OpenStreetMap (Overpass, amenity=parking)",
        "license": "ODbL 1.0 © OpenStreetMap contributors",
        "coverage": {"territory": "euskadi", "notes": "Cobertura según densidad de mapeo en OSM."},
    },
    {
        "id": "pois-euskadi-bikepark",
        "title": "Aparcabicis (Euskadi)",
        "src": "data/pois-euskadi/bikepark.json",
        "records_field": "pois",
        "source": "OpenStreetMap (Overpass, amenity=bicycle_parking)",
        "license": "ODbL 1.0 © OpenStreetMap contributors",
        "coverage": {"territory": "euskadi", "notes": "Cobertura según densidad de mapeo en OSM."},
    },
    {
        "id": "pois-euskadi-beaches",
        "title": "Playas (Euskadi)",
        "src": "data/pois-euskadi/beaches.json",
        "records_field": "pois",
        "source": "OpenStreetMap + Open Data Bizkaia (DFB)",
        "license": "ODbL 1.0 / CC BY 4.0",
        "coverage": {"territory": "euskadi", "notes": "Costa de Bizkaia y Gipuzkoa."},
    },
    {
        "id": "neighborhoods-bizkaia",
        "title": "Límites administrativos de Bizkaia (municipios, distritos, barrios)",
        "src": "data/processed/neighborhoods/neighborhoods.json",
        "records_field": "features",
        "source": "OpenStreetMap (Overpass)",
        "license": "ODbL 1.0 © OpenStreetMap contributors",
        "coverage": {
            "territory": "bizkaia",
            "notes": "113 municipios y 8 distritos completos; 26/~34 barrios de Bilbao.",
        },
    },
    {
        "id": "pois-madrid-fountains",
        "title": "Fuentes de agua para beber del Ayuntamiento de Madrid",
        "src": "data/processed/madrid/pois/fountains.json",
        "records_field": "pois",
        "source": "Ayuntamiento de Madrid — dataset 300051-0",
        "license": "CC BY 4.0 (Ayuntamiento de Madrid)",
        "coverage": {
            "territory": "madrid",
            "notes": (
                "Inventario municipal oficial; completeness no estimada "
                "sin un universo independiente."
            ),
        },
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def quality(records: list) -> dict:
    """Calidad simple: nº de registros y % medio de campos top-level vacíos."""
    n = len(records)
    if not n:
        return {"records": 0, "emptyFieldsPct": 0.0}
    empties = total = 0
    for r in records:
        if not isinstance(r, dict):
            continue
        for v in r.values():
            total += 1
            if v is None or v == "" or v == [] or v == {}:
                empties += 1
    pct = round(100 * empties / total, 2) if total else 0.0
    return {"records": n, "emptyFieldsPct": pct}


def _release_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("fecha esperada: YYYY-MM-DD") from exc


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Normaliza metadatos del tar para que dos builds iguales den el mismo hash."""
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="semver sin prefijo v")
    parser.add_argument(
        "--date",
        type=_release_date,
        default=date.today().isoformat(),
        help="fecha reproducible de release (YYYY-MM-DD)",
    )
    args = parser.parse_args()
    if not VERSION_RE.fullmatch(args.version):
        parser.error("--version debe ser semver, por ejemplo 0.3.0-rc.1")
    return args


def main() -> None:
    args = parse_args()
    version = args.version
    out_dir = LABS / "releases" / f"v{version}"
    stage = DIST / f"emap-labs-datasets-v{version}"
    print(f"emap-next: {EMAP_NEXT}")
    if not EMAP_NEXT.exists():
        raise SystemExit(f"No encuentro emap-next en {EMAP_NEXT}")

    if stage.exists():
        shutil.rmtree(stage)
    (stage / "data").mkdir(parents=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for ds in DATASETS:
        src = EMAP_NEXT / ds["src"]
        raw = json.loads(src.read_text())
        records = raw.get(ds["records_field"], [])
        dst_name = f"{ds['id']}.json"
        shutil.copy2(src, stage / "data" / dst_name)
        entry = {
            "id": ds["id"],
            "title": ds["title"],
            "file": f"data/{dst_name}",
            "format": "GeoJSON" if ds["records_field"] == "features" else "JSON (pois[])",
            "source": ds["source"],
            "license": ds["license"],
            "updated": (
                raw.get("source_updated")
                or raw.get("updated")
                or raw.get("generated")
                or date.fromtimestamp(src.stat().st_mtime).isoformat()
            ),
            "sizeBytes": src.stat().st_size,
            "checksum": {"algo": "sha256", "value": sha256(src)},
            "coverage": ds["coverage"],
            "quality": quality(records),
        }
        entries.append(entry)
        print(f"  ✓ {ds['id']:26} {entry['quality']['records']:>5} reg  "
              f"{entry['quality']['emptyFieldsPct']:>5}% vacío  {ds['license'][:32]}")

    manifest = {
        "release": f"v{version}",
        "status": "prerelease" if "-" in version else "stable",
        "project": "EMAP Labs — datasets",
        "generatedAt": args.date,
        "territories": ["euskadi", "madrid"],
        "datasets": entries,
        "totals": {
            "datasets": len(entries),
            "records": sum(e["quality"]["records"] for e in entries),
        },
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(manifest_path, stage / "manifest.json")
    notes = LABS / "releases" / "RELEASE-NOTES.md"
    if notes.exists():
        shutil.copy2(notes, stage / "README.md")

    # Tarball descargable
    DIST.mkdir(exist_ok=True)
    tar_path = DIST / f"emap-labs-datasets-v{version}.tar.gz"
    with tar_path.open("wb") as raw_out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                tar.add(stage, arcname=stage.name, filter=_tar_filter)

    print(f"\nmanifest → {manifest_path}")
    print(f"tarball  → {tar_path}  ({tar_path.stat().st_size // 1024} KB)")
    print(f"total: {manifest['totals']['datasets']} datasets, "
          f"{manifest['totals']['records']} registros")


if __name__ == "__main__":
    main()
