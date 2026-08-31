"""Contrato del runtime multi-territorio servido por EMAP Intelligence."""

from __future__ import annotations

import sys
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from regions import load_territory  # noqa: E402
from service.runtime import (  # noqa: E402
    RuntimeRegistry,
    TerritoryResolutionError,
)
from semantic_local import HybridRetrieverFactory  # noqa: E402


@dataclass(frozen=True)
class _RuntimeStub:
    territory: object


class _RetrieverStub:
    name = "fake"

    def __init__(self, datasets):
        self.datasets = datasets


def _retriever_factory(_profile: str, datasets):
    return _RetrieverStub(datasets)


class RuntimeRegistryResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.euskadi = _RuntimeStub(load_territory("euskadi"))
        self.madrid = _RuntimeStub(load_territory("madrid"))
        self.registry = RuntimeRegistry(
            {"euskadi": self.euskadi, "madrid": self.madrid}
        )

    def test_resuelve_por_id_explicito_sin_fallback(self) -> None:
        self.assertIs(self.euskadi, self.registry.resolve(territory_id="euskadi"))
        self.assertIs(self.madrid, self.registry.resolve(territory_id="madrid"))

        with self.assertRaisesRegex(TerritoryResolutionError, "unknown_territory"):
            self.registry.resolve(territory_id="desconocido")

    def test_resuelve_por_bbox_y_rechaza_coordenadas_fuera_de_cobertura(self) -> None:
        self.assertIs(
            self.euskadi,
            self.registry.resolve(lat=43.263, lon=-2.935),
        )
        self.assertIs(
            self.madrid,
            self.registry.resolve(lat=40.4168, lon=-3.7038),
        )

        with self.assertRaisesRegex(TerritoryResolutionError, "territory_unresolved"):
            self.registry.resolve(lat=41.3874, lon=2.1686)

    def test_rechaza_mismatch_y_coordenadas_incompletas(self) -> None:
        with self.assertRaisesRegex(TerritoryResolutionError, "territory_mismatch"):
            self.registry.resolve(
                territory_id="madrid", lat=43.263, lon=-2.935
            )

        with self.assertRaisesRegex(TerritoryResolutionError, "invalid_coordinates"):
            self.registry.resolve(lat=40.4168)


class RuntimeRegistryBuildTest(unittest.TestCase):
    def test_carga_datasets_aislados_y_version_del_manifiesto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            euskadi_path = data_root / "pois-euskadi/fountains.json"
            madrid_path = data_root / "processed/madrid/pois/fountains.json"
            madrid_parking_path = data_root / "processed/madrid/pois/parking.json"
            madrid_bikepark_path = data_root / "processed/madrid/pois/bikepark.json"
            euskadi_path.parent.mkdir(parents=True)
            madrid_path.parent.mkdir(parents=True)
            euskadi_path.write_text(json.dumps({"pois": [_poi("Fuente Euskadi")]}))
            madrid_path.write_text(json.dumps({"pois": [_poi("Fuente Madrid")]}))
            madrid_parking_path.write_text(
                json.dumps({"pois": [_poi("Parking Madrid")]})
            )
            madrid_bikepark_path.write_text(
                json.dumps({"pois": [_poi("Bikepark Madrid")]})
            )

            registry = RuntimeRegistry.build(
                data_root=data_root,
                territory_ids=("euskadi", "madrid"),
                retriever_factory=_retriever_factory,
            )

            health = registry.health()

        euskadi = registry.resolve(territory_id="euskadi")
        madrid = registry.resolve(territory_id="madrid")
        self.assertEqual("0.2.0", euskadi.territory.version)
        self.assertEqual("0.3.0", madrid.territory.version)
        self.assertEqual("Fuente Euskadi", euskadi.datasets["fountains"][0]["name"])
        self.assertEqual("Fuente Madrid", madrid.datasets["fountains"][0]["name"])
        self.assertIsNot(euskadi.datasets, madrid.datasets)
        self.assertEqual("0.2.0", health["euskadi"]["territory_version"])
        self.assertEqual("0.3.0", health["madrid"]["territory_version"])
        self.assertEqual(3, health["madrid"]["pois"])
        self.assertTrue(health["madrid"]["ok"])
        self.assertFalse(health["euskadi"]["ok"])

    def test_comparte_encoder_por_perfil_sin_compartir_retriever(self) -> None:
        encoder = _EncoderStub()
        factory = HybridRetrieverFactory(encoder_factory=lambda _profile: encoder)

        first = factory("e5large", {"fountains": (_poi("Primera"),)})
        second = factory("e5large", {"fountains": (_poi("Segunda"),)})

        self.assertIsNot(first, second)
        self.assertIs(encoder, first.encoder)
        self.assertIs(encoder, second.encoder)
        self.assertIsNot(first.datasets, second.datasets)


def _poi(name: str) -> dict:
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "lat": 40.4,
        "lon": -3.7,
        "tags": {},
    }


class _EncoderStub:
    profile_name = "e5large"
    sim_threshold = 0.8
    tie_window = 0.01

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _text in texts]

    def embed_query(self, _text):
        return [1.0, 0.0]


if __name__ == "__main__":
    unittest.main()
