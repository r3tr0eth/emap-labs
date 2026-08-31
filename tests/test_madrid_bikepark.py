"""Contrato del adapter oficial de aparcabicis municipales de Madrid."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEO_PACKAGE = ROOT.parent / "emap-next" / "packages" / "geo"
CATALOG_PACKAGE = ROOT.parent / "emap-next" / "packages" / "data-catalog"
sys.path[:0] = [str(GEO_PACKAGE), str(CATALOG_PACKAGE)]
MODULE_PATH = ROOT / "datasets" / "madrid-bikepark" / "build.py"
SPEC = importlib.util.spec_from_file_location("madrid_bikepark_build", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

from data_catalog.schemas import validation_errors  # noqa: E402


class MadridBikeparkAdapterTest(unittest.TestCase):
    def test_normaliza_utm_y_conserva_estado_oficial(self) -> None:
        poi = MODULE.normalise_record(
            {
                "ID": "10047501",
                "DESC_CLASIFICACION": "Aparcabicicletas",
                "ESTADO": "OPERATIVO",
                "COORD_GIS_X": "444489.152",
                "COORD_GIS_Y": "4476437.442",
                "LATITUD": None,
                "LONGITUD": None,
                "TIPO_VIA": "CALLE",
                "NOM_VIA": "VIRGEN DEL VAL",
                "NUM_VIA": "3",
                "COD_POSTAL": "28027",
                "DISTRITO": "CIUDAD LINEAL",
                "BARRIO": "SAN PASCUAL",
                "FECHA_INSTALACION": 1749427200000,
                "FX_CARGA": "28/08/2026",
            }
        )

        assert poi is not None
        self.assertEqual("bikepark:10047501", poi["id"])
        self.assertEqual("bikepark", poi["layer_id"])
        self.assertEqual("bike_parking", poi["category"])
        self.assertTrue(poi["tags"]["operational"])
        self.assertEqual("derived_etrs89_utm30n", poi["tags"]["coordinate_source"])
        self.assertEqual("2025-06-09", poi["tags"]["installed_on"])
        self.assertEqual([], validation_errors("poi.schema.json", poi))

    def test_documento_determinista_deduplica_y_explica_descartes(self) -> None:
        records = [
            {
                "ID": "1",
                "DESC_CLASIFICACION": "Aparcabicicletas",
                "ESTADO": "OPERATIVO",
                "COORD_GIS_X": "444489.152",
                "COORD_GIS_Y": "4476437.442",
            },
            {
                "ID": "1",
                "ESTADO": "OPERATIVO",
                "COORD_GIS_X": "444489.152",
                "COORD_GIS_Y": "4476437.442",
            },
            {"ID": "sin-coordenadas"},
            {},
        ]
        raw = json.dumps(records, separators=(",", ":")).encode()
        first = MODULE.build_document(
            raw,
            source_updated="2026-08-28",
            ingested_at="2026-08-29T08:00:00Z",
        )
        second = MODULE.build_document(
            raw,
            source_updated="2026-08-28",
            ingested_at="2026-08-29T08:00:00Z",
        )

        self.assertEqual(first, second)
        self.assertEqual(4, first["source_records"])
        self.assertEqual(1, first["accepted_records"])
        self.assertEqual(3, first["discarded_records"])
        self.assertEqual(
            {"duplicate_id": 1, "invalid_coordinates": 1, "missing_id": 1},
            first["discard_reasons"],
        )
        self.assertEqual(2, first["freshness_sla_days"])


if __name__ == "__main__":
    unittest.main()
