"""Configuración territorial reutilizable de EMAP Labs."""

from .registry import (
    Territory,
    TerritoryConfigError,
    list_territories,
    load_territory,
    resolve_layer_path,
)

__all__ = [
    "Territory",
    "TerritoryConfigError",
    "list_territories",
    "load_territory",
    "resolve_layer_path",
]
