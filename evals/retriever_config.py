"""Carga perfiles reproducibles de modelo + calibración de abstención."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CONFIG_PATH = Path(__file__).with_name("retriever-config.json")


class RetrieverConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RetrieverProfile:
    name: str
    model: str
    sim_threshold: float
    tie_window: float


@lru_cache(maxsize=1)
def _config() -> dict:
    doc = json.loads(CONFIG_PATH.read_text())
    if not isinstance(doc.get("profiles"), dict) or not doc["profiles"]:
        raise RetrieverConfigError("retriever-config.json no contiene perfiles")
    return doc


def profile_names() -> tuple[str, ...]:
    return tuple(sorted(_config()["profiles"]))


def resolve_profile(
    profile_name: str | None = None,
    model: str | None = None,
) -> RetrieverProfile:
    """Resuelve por nombre o modelo; un modelo desconocido exige calibración."""
    doc = _config()
    profiles = doc["profiles"]
    selected_name = profile_name
    if selected_name is None and model is not None:
        selected_name = next(
            (name for name, values in profiles.items() if values.get("model") == model),
            None,
        )
        if selected_name is None:
            raise RetrieverConfigError(
                f"modelo sin perfil calibrado: {model}; añade un perfil versionado"
            )
    selected_name = selected_name or doc.get("default_profile")
    if selected_name not in profiles:
        raise RetrieverConfigError(f"perfil desconocido: {selected_name}")
    values = profiles[selected_name]
    configured_model = str(values["model"])
    if model is not None and model != configured_model:
        raise RetrieverConfigError(
            f"el perfil {selected_name} usa {configured_model}, no {model}"
        )
    return RetrieverProfile(
        name=str(selected_name),
        model=configured_model,
        sim_threshold=float(values["sim_threshold"]),
        tie_window=float(values["tie_window"]),
    )
