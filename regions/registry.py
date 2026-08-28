"""Registro territorial: única interfaz entre configuración y runtime.

El manifiesto de cada territorio describe qué datos consume el pipeline.
Los adapters de ingesta producen esos ficheros; servicio, evals y módulos de
evidencia no necesitan conocer rutas específicas de Euskadi o Madrid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml


REGIONS_DIR = Path(__file__).resolve().parent
_VALID_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class TerritoryConfigError(ValueError):
    """El manifiesto territorial no es seguro o no cumple el contrato."""


@dataclass(frozen=True)
class Territory:
    id: str
    version: str
    name: str
    territory: str
    languages: tuple[str, ...]
    bbox: tuple[float, float, float, float]
    layers: Mapping[str, str]
    evaluation: Mapping[str, str]
    production_retriever_profile: str
    freshness_sla_days: Mapping[str, int]
    attribution: str

    def evaluation_path(self, key: str) -> Path:
        rel = self.evaluation.get(key)
        if not rel:
            raise TerritoryConfigError(
                f"regions/{self.id}: falta evaluation.{key}"
            )
        return _safe_repo_path(rel, f"evaluation.{key}")


def _safe_repo_path(raw: str, field: str) -> Path:
    rel = Path(str(raw))
    if rel.is_absolute() or ".." in rel.parts:
        raise TerritoryConfigError(f"{field}: la ruta debe ser relativa al repo")
    return REGIONS_DIR.parent / rel


def _read_bbox(raw: object, territory_id: str) -> tuple[float, float, float, float]:
    if not isinstance(raw, list) or len(raw) != 4:
        raise TerritoryConfigError(
            f"regions/{territory_id}: bbox debe ser "
            "[min_lon, min_lat, max_lon, max_lat]"
        )
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in raw)
    if not (-180 <= min_lon < max_lon <= 180):
        raise TerritoryConfigError(f"regions/{territory_id}: bbox de longitud inválido")
    if not (-90 <= min_lat < max_lat <= 90):
        raise TerritoryConfigError(f"regions/{territory_id}: bbox de latitud inválido")
    return min_lon, min_lat, max_lon, max_lat


def _read_paths(raw: object, field: str, *, required: bool) -> Mapping[str, str]:
    if not isinstance(raw, dict) or (required and not raw):
        raise TerritoryConfigError(f"{field}: se esperaba un mapa no vacío")
    paths: dict[str, str] = {}
    for key, value in raw.items():
        rel = Path(str(value))
        if rel.is_absolute() or ".." in rel.parts:
            raise TerritoryConfigError(f"{field}.{key}: ruta insegura")
        paths[str(key)] = rel.as_posix()
    return MappingProxyType(paths)


@lru_cache(maxsize=None)
def load_territory(territory_id: str) -> Territory:
    """Carga y valida un territorio listo para ser consumido por EMAP Core."""
    if not _VALID_ID.fullmatch(territory_id):
        raise TerritoryConfigError(f"id territorial inválido: {territory_id!r}")
    path = REGIONS_DIR / territory_id / "region.yaml"
    if not path.is_file():
        raise TerritoryConfigError(f"regions/{territory_id}/region.yaml no existe")
    doc = yaml.safe_load(path.read_text())
    if not isinstance(doc, dict):
        raise TerritoryConfigError(f"regions/{territory_id}: manifiesto inválido")
    if not doc.get("version"):
        raise TerritoryConfigError(f"regions/{territory_id}: falta version")
    if not doc.get("attribution"):
        raise TerritoryConfigError(f"regions/{territory_id}: falta attribution")

    languages = doc.get("languages")
    if not isinstance(languages, list) or not languages or "es" not in languages:
        raise TerritoryConfigError(
            f"regions/{territory_id}: languages debe incluir al menos es"
        )

    retrieval = doc.get("retrieval") or {}
    if not isinstance(retrieval, dict):
        raise TerritoryConfigError(f"regions/{territory_id}: retrieval inválido")
    if not retrieval.get("production_profile"):
        raise TerritoryConfigError(
            f"regions/{territory_id}: falta retrieval.production_profile"
        )

    freshness = doc.get("freshness_sla_days") or {}
    if not isinstance(freshness, dict):
        raise TerritoryConfigError(
            f"regions/{territory_id}: freshness_sla_days inválido"
        )

    return Territory(
        id=territory_id,
        version=str(doc["version"]),
        name=str(doc.get("name") or territory_id),
        territory=str(doc.get("territory") or doc.get("name") or territory_id),
        languages=tuple(str(lang) for lang in languages),
        bbox=_read_bbox(doc.get("bbox"), territory_id),
        layers=_read_paths(doc.get("layers"), f"regions/{territory_id}.layers", required=True),
        evaluation=_read_paths(
            doc.get("evaluation") or {},
            f"regions/{territory_id}.evaluation",
            required=True,
        ),
        production_retriever_profile=str(retrieval["production_profile"]),
        freshness_sla_days=MappingProxyType(
            {str(layer): int(days) for layer, days in freshness.items()}
        ),
        attribution=str(doc["attribution"]),
    )


def list_territories(*, runnable_only: bool = False) -> list[str]:
    """Lista manifiestos; opcionalmente solo los que pasan el contrato runtime."""
    ids = sorted(
        path.parent.name for path in REGIONS_DIR.glob("*/region.yaml")
        if path.parent.is_dir()
    )
    if not runnable_only:
        return ids
    runnable: list[str] = []
    for territory_id in ids:
        try:
            load_territory(territory_id)
        except TerritoryConfigError:
            continue
        runnable.append(territory_id)
    return runnable


def resolve_layer_path(data_root: Path, territory: Territory, layer: str) -> Path | None:
    """Resuelve una capa configurada sin conocer su layout territorial."""
    rel = territory.layers.get(layer)
    return data_root / rel if rel else None
