#!/usr/bin/env python3
"""Kit de replicación territorial.

Hace que añadir una nueva región sea configuración y datos,
no reescribir el sistema.

Estructura estándar de región:
    regions/<id>/
        region.yaml          # metadatos, bbox, idiomas, calibración
        sources.yaml         # fuentes de datos específicos
        evals/               # corpus dorado local (si existe)
        data/                # datos procesados locales

Comandos:
    python region_kit.py validate <region>   # valida estructura y datos
    python region_kit.py scaffold <region>   # crea template para nueva región
    python region_kit.py list                # lista regiones disponibles
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REGIONS_DIR = Path(__file__).resolve().parent / "regions"
# Si se ejecuta desde fuera, __file__ puede ser relativo. Forzar absoluto.
if not REGIONS_DIR.exists():
    REGIONS_DIR = Path(__file__).resolve().parent.parent / "regions"

# Schema mínimo requerido
REQUIRED_FIELDS = ["name", "territory", "languages", "bbox"]
REQUIRED_LAYERS = ["fountains", "toilets", "parking"]  # mínimo viable


def load_region(region_id: str) -> dict | None:
    """Carga region.yaml de una región."""
    path = REGIONS_DIR / region_id / "region.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())


def list_regions() -> list[str]:
    """Lista regiones disponibles."""
    if not REGIONS_DIR.exists():
        return []
    regions = []
    for d in sorted(REGIONS_DIR.iterdir()):
        if d.is_dir() and (d / "region.yaml").exists():
            regions.append(d.name)
    return regions


def validate_region(region_id: str) -> tuple[bool, list[str]]:
    """Valida que una región cumple el estándar.

    Returns:
        (es_válido, lista_de_problemas)
    """
    problems = []

    region = load_region(region_id)
    if region is None:
        return False, [f"regions/{region_id}/region.yaml no existe"]

    # Campos requeridos
    for field in REQUIRED_FIELDS:
        if field not in region:
            problems.append(f"falta campo requerido: {field}")

    # BBOX válido
    bbox = region.get("bbox")
    if bbox:
        if len(bbox) != 4:
            problems.append("bbox debe tener 4 valores [min_lon, min_lat, max_lon, max_lat]")
        elif not (-180 <= bbox[0] <= 180 and -180 <= bbox[2] <= 180):
            problems.append("bbox: longitudes fuera de rango")
        elif not (-90 <= bbox[1] <= 90 and -90 <= bbox[3] <= 90):
            problems.append("bbox: latitudes fuera de rango")

    # Idiomas
    langs = region.get("languages", [])
    if not langs or "es" not in langs:
        problems.append("languages debe incluir al menos 'es'")

    # Calibración solar (si existe)
    solar = region.get("solar_calibration")
    if solar:
        if "model" not in solar:
            problems.append("solar_calibration requiere model")
        if "tau" not in solar:
            problems.append("solar_calibration requiere tau")

    # Datos mínimos
    data_dir = REGIONS_DIR / region_id / "data"
    if data_dir.exists():
        for layer in REQUIRED_LAYERS:
            layer_path = data_dir / f"{layer}.json"
            if not layer_path.exists():
                problems.append(f"falta capa mínima: data/{layer}.json")
    # No es error si no existe data/ (puede usar datos globales)

    return len(problems) == 0, problems


def scaffold_region(region_id: str, name: str, territory: str,
                    languages: list[str], bbox: list[float]) -> Path:
    """Crea el template para una nueva región."""
    region_dir = REGIONS_DIR / region_id
    if region_dir.exists():
        raise FileExistsError(f"regions/{region_id} ya existe")

    region_dir.mkdir(parents=True)

    config = {
        "name": name,
        "territory": territory,
        "languages": languages,
        "bbox": bbox,
        "sources": {
            "transit": "configurar-fuente-gtfs",
            "pois": "osm-overpass",
        },
        "eval_split": {"dev": 0, "heldout": 0},
        "solar_calibration": {
            "model": "intfloat/multilingual-e5-large",
            "tau": 0.80,
            "tie": 0.01,
            "note": "recalibrar con datos locales",
        },
        "attribution": "configurar-atribución",
    }

    path = region_dir / "region.yaml"
    path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    # Crear subdirectorías
    (region_dir / "data").mkdir(exist_ok=True)
    (region_dir / "evals").mkdir(exist_ok=True)

    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Kit de replicación territorial")
    sub = parser.add_subparsers(dest="command")

    p_validate = sub.add_parser("validate", help="Valida una región")
    p_validate.add_argument("region")

    p_scaffold = sub.add_parser("scaffold", help="Crea template de región")
    p_scaffold.add_argument("region_id")
    p_scaffold.add_argument("--name", required=True)
    p_scaffold.add_argument("--territory", required=True)
    p_scaffold.add_argument("--languages", nargs="+", required=True)
    p_scaffold.add_argument("--bbox", nargs=4, type=float, required=True)

    sub.add_parser("list", help="Lista regiones")

    args = parser.parse_args()

    if args.command == "list":
        regions = list_regions()
        if not regions:
            print("No hay regiones configuradas")
            return 1
        for r in regions:
            print(f"  {r}")
        return 0

    if args.command == "validate":
        valid, problems = validate_region(args.region)
        if valid:
            print(f"✅ regions/{args.region} válida")
        else:
            print(f"❌ regions/{args.region} tiene problemas:")
            for p in problems:
                print(f"   - {p}")
        return 0 if valid else 1

    if args.command == "scaffold":
        try:
            path = scaffold_region(args.region_id, args.name, args.territory,
                                   args.languages, args.bbox)
            print(f"✅ Creado: {path}")
            print(f"   Edita region.yaml y añade tus datos en data/")
        except FileExistsError as e:
            print(f"❌ {e}")
            return 1
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
