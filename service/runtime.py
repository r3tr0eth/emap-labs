"""Runtime territorial aislado para una única instancia de Intelligence.

La interfaz pública del módulo es ``RuntimeRegistry.resolve``. Los callers no
conocen cómo se cargan datasets, retrievers o caches: únicamente reciben el
runtime inmutable del territorio resuelto para la petición.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, TypeVar

from regions import Territory, load_territory, resolve_layer_path


class TerritoryRuntimeLike(Protocol):
    """Superficie mínima que el registro necesita de un runtime."""

    territory: object


RuntimeT = TypeVar("RuntimeT", bound=TerritoryRuntimeLike)
RetrieverFactory = Callable[[str, Mapping[str, tuple[dict, ...]]], Any]


class TerritoryResolutionError(ValueError):
    """La petición no puede asociarse inequívocamente a un territorio."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class TerritoryRuntime:
    """Estado de retrieval perteneciente exclusivamente a un territorio."""

    territory: Territory
    datasets: Mapping[str, tuple[dict, ...]]
    documents: Mapping[str, Mapping[str, Any]]
    counts: Mapping[str, int]
    missing_files: tuple[str, ...]
    retriever: Any


class RuntimeRegistry:
    """Registro inmutable de runtimes disponibles en el proceso servido."""

    def __init__(self, runtimes: Mapping[str, RuntimeT]) -> None:
        if not runtimes:
            raise ValueError("RuntimeRegistry requiere al menos un territorio")
        for territory_id, runtime in runtimes.items():
            runtime_id = getattr(runtime.territory, "id", None)
            if runtime_id != territory_id:
                raise ValueError(
                    f"runtime {territory_id!r} declara territory.id={runtime_id!r}"
                )
        self._runtimes = MappingProxyType(dict(runtimes))

    @classmethod
    def build(
        cls,
        *,
        data_root: Path,
        territory_ids: tuple[str, ...],
        retriever_factory: RetrieverFactory,
    ) -> "RuntimeRegistry":
        """Carga runtimes aislados y reutiliza el factory semántico inyectado."""
        runtimes: dict[str, TerritoryRuntime] = {}
        for territory_id in territory_ids:
            territory = load_territory(territory_id)
            datasets: dict[str, tuple[dict, ...]] = {}
            documents: dict[str, Mapping[str, Any]] = {}
            missing_files: list[str] = []
            for layer in territory.layers:
                path = resolve_layer_path(data_root, territory, layer)
                assert path is not None
                if not path.is_file():
                    missing_files.append(str(path.relative_to(data_root)))
                    continue
                document = json.loads(path.read_text())
                raw_pois = document.get("pois")
                if not isinstance(raw_pois, list):
                    raise ValueError(f"{path}: falta una lista pois")
                pois = tuple(
                    _normalized_poi(poi, layer=layer, index=index)
                    for index, poi in enumerate(raw_pois)
                )
                datasets[layer] = pois
                documents[layer] = MappingProxyType(document)
            frozen_datasets = MappingProxyType(datasets)
            runtime = TerritoryRuntime(
                territory=territory,
                datasets=frozen_datasets,
                documents=MappingProxyType(documents),
                counts=MappingProxyType(
                    {layer: len(pois) for layer, pois in datasets.items()}
                ),
                missing_files=tuple(missing_files),
                retriever=retriever_factory(
                    territory.production_retriever_profile, frozen_datasets
                ),
            )
            runtimes[territory_id] = runtime
        return cls(runtimes)

    def resolve(
        self,
        *,
        territory_id: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> RuntimeT:
        """Resuelve un runtime explícito; nunca aplica fallback territorial."""
        if (lat is None) != (lon is None):
            raise TerritoryResolutionError(
                "invalid_coordinates", "lat y lon deben enviarse conjuntamente"
            )
        if lat is not None and lon is not None:
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise TerritoryResolutionError(
                    "invalid_coordinates", "lat o lon fuera de rango"
                )
        if territory_id is not None:
            runtime = self._runtimes.get(territory_id)
            if runtime is None:
                raise TerritoryResolutionError(
                    "unknown_territory", f"territorio no servido: {territory_id}"
                )
            if lat is not None and lon is not None and not _contains(
                runtime.territory.bbox, lat=lat, lon=lon
            ):
                raise TerritoryResolutionError(
                    "territory_mismatch",
                    f"las coordenadas no pertenecen a {territory_id}",
                )
            return runtime
        if lat is not None and lon is not None:
            matches = [
                runtime
                for runtime in self._runtimes.values()
                if _contains(runtime.territory.bbox, lat=lat, lon=lon)
            ]
            if len(matches) == 1:
                return matches[0]
            if not matches:
                raise TerritoryResolutionError(
                    "territory_unresolved",
                    "las coordenadas no pertenecen a un territorio servido",
                )
            raise TerritoryResolutionError(
                "territory_ambiguous",
                "las coordenadas pertenecen a más de un territorio servido",
            )
        raise TerritoryResolutionError(
            "territory_required", "indica territory o unas coordenadas resolubles"
        )

    def health(self) -> dict[str, dict[str, Any]]:
        """Estado operativo por territorio, sin colapsar versiones ni capas."""
        report: dict[str, dict[str, Any]] = {}
        for territory_id, runtime in self._runtimes.items():
            missing = list(runtime.missing_files)
            report[territory_id] = {
                "ok": not missing,
                "territory_version": runtime.territory.version,
                "layers": dict(runtime.counts),
                "pois": sum(runtime.counts.values()),
                "retriever": runtime.retriever.name,
                "missing_files": missing,
                "expected_layers": len(runtime.territory.layers),
                "loaded_layers": len(runtime.counts),
            }
        return report


def _contains(
    bbox: tuple[float, float, float, float], *, lat: float, lon: float
) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _normalized_poi(poi: object, *, layer: str, index: int) -> dict:
    if not isinstance(poi, dict):
        raise ValueError(f"{layer}[{index}]: POI inválido")
    normalized = dict(poi)
    normalized.setdefault("id", f"{layer}:{index}")
    return normalized
