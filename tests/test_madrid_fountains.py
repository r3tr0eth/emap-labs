"""Contrato del adapter oficial de fuentes de Madrid."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEO_PACKAGE = ROOT.parent / "emap-next" / "packages" / "geo"
sys.path.insert(0, str(GEO_PACKAGE))
MODULE_PATH = ROOT / "datasets" / "madrid-fountains" / "build.py"
SPEC = importlib.util.spec_from_file_location("madrid_fountains_build", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
sys.path.insert(0, str(ROOT / "evals"))
from baseline import BaselineRetriever  # noqa: E402


class MadridFountainsAdapterTest(unittest.TestCase):
    def test_prioriza_coordenadas_publicadas_y_conserva_evidencia(self) -> None:
        poi = MODULE.normalise_record(
            {
                "ID": "10046448",
                "ESTADO": "OPERATIVO",
                "LATITUD": 40.41042569,
                "LONGITUD": -3.71556256,
                "COORD_GIS_X": "439286.799",
                "COORD_GIS_Y": "4473557.836",
                "DISTRITO": "CENTRO",
                "BARRIO": "PALACIO",
                "DIRECCION_AUX": "Parque de la Cornisa",
                "TIPO_VIA": "CALLE",
                "NOM_VIA": "JERTE",
                "NUM_VIA": "3",
            }
        )

        assert poi is not None
        self.assertEqual("fountains:10046448", poi["id"])
        self.assertEqual("madrid_fountains_official", poi["source_id"])
        self.assertEqual("madrid", poi["territory"])
        self.assertTrue(poi["tags"]["operational"])
        self.assertEqual("published_wgs84", poi["tags"]["coordinate_source"])
        self.assertIn("Parque de la Cornisa", poi["address"])

    def test_recupera_por_utm_un_registro_sin_latitud_longitud(self) -> None:
        poi = MODULE.normalise_record(
            {
                "ID": "utm-only",
                "ESTADO": "FUERA_DE_SERVICIO",
                "COORD_GIS_X": "439286.799",
                "COORD_GIS_Y": "4473557.836",
                "DIRECCION_AUX": "Parque de la Cornisa",
            }
        )

        assert poi is not None
        self.assertAlmostEqual(40.41042569, poi["lat"], places=6)
        self.assertAlmostEqual(-3.71556256, poi["lon"], places=6)
        self.assertFalse(poi["tags"]["operational"])
        self.assertEqual("out_of_service", poi["tags"]["status"])
        self.assertEqual("derived_etrs89_utm30n", poi["tags"]["coordinate_source"])

    def test_estado_truncado_se_trata_como_cierre_temporal(self) -> None:
        status, operational = MODULE._normalised_status("CERRADA_TEMPORALMENT")
        self.assertEqual("temporarily_closed", status)
        self.assertFalse(operational)

    def test_documento_es_determinista_deduplica_y_descarta_invalido(self) -> None:
        records = [
            {
                "ID": "2",
                "ESTADO": "NO_PREPARADO",
                "LATITUD": 40.42,
                "LONGITUD": -3.70,
                "DIRECCION_AUX": "Dos",
            },
            {
                "ID": "1",
                "ESTADO": "OPERATIVO",
                "LATITUD": 40.41,
                "LONGITUD": -3.71,
                "DIRECCION_AUX": "Uno",
            },
            {
                "ID": "1",
                "ESTADO": "OPERATIVO",
                "LATITUD": 40.41,
                "LONGITUD": -3.71,
            },
            {"ID": "sin-coordenadas"},
        ]
        raw = json.dumps(records, separators=(",", ":")).encode()

        first = MODULE.build_document(raw, "2026-08-28")
        second = MODULE.build_document(raw, "2026-08-28")

        self.assertEqual(first, second)
        self.assertEqual(["fountains:1", "fountains:2"], [p["id"] for p in first["pois"]])
        self.assertEqual(2, first["count"])
        self.assertEqual(2, first["dropped"])
        self.assertEqual({"not_ready": 1, "operational": 1}, first["status_counts"])


class MadridFountainsRetrievalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.retriever = BaselineRetriever(
            {
                "fountains": [
                    {
                        "id": "fountains:operativa",
                        "name": {"es": "Fuente operativa"},
                        "lat": 40.410,
                        "lon": -3.710,
                        "tags": {"operational": True},
                    },
                    {
                        "id": "fountains:cerrada",
                        "name": {"es": "Fuente cerrada"},
                        "lat": 40.411,
                        "lon": -3.711,
                        "tags": {"operational": False},
                    },
                ]
            }
        )
        self.anchor = {"lat": 40.411, "lon": -3.711}

    def test_filtra_fuentes_operativas_antes_de_ordenar_por_distancia(self) -> None:
        results = self.retriever.retrieve("fuente operativa", self.anchor)
        self.assertEqual(["fountains:operativa"], [poi["id"] for poi in results])

    def test_filtra_fuentes_fuera_de_servicio(self) -> None:
        results = self.retriever.retrieve("fuente fuera de servicio", self.anchor)
        self.assertEqual(["fountains:cerrada"], [poi["id"] for poi in results])

    def test_la_negacion_no_activa_despues_el_filtro_positivo(self) -> None:
        results = self.retriever.retrieve("fuente no operativa", self.anchor)
        self.assertEqual(["fountains:cerrada"], [poi["id"] for poi in results])


if __name__ == "__main__":
    unittest.main()
