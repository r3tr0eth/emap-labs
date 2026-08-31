"""Contrato del adapter de aparcamientos municipales de Madrid."""

from __future__ import annotations

import importlib.util
import csv
import io
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEO_PACKAGE = ROOT.parent / "emap-next" / "packages" / "geo"
CATALOG_PACKAGE = ROOT.parent / "emap-next" / "packages" / "data-catalog"
sys.path[:0] = [str(GEO_PACKAGE), str(CATALOG_PACKAGE), str(ROOT / "evals")]
MODULE_PATH = ROOT / "datasets" / "madrid-parking" / "build.py"
SPEC = importlib.util.spec_from_file_location("madrid_parking_build", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

from data_catalog.schemas import validation_errors  # noqa: E402


class MadridParkingAdapterTest(unittest.TestCase):
    def test_normaliza_parking_publico_con_schema_comun(self) -> None:
        poi = MODULE.normalise_record(
            {
                "PK": "11483771",
                "NOMBRE": "Aparcamiento disuasorio Aviación Española",
                "HORARIO": "Abierto 24 horas",
                "DESCRIPCION": "Plazas para automóviles: 344",
                "ACCESIBILIDAD": "1",
                "CONTENT-URL": "https://www.madrid.es/aparcamiento/11483771",
                "NOMBRE-VIA": "FUENTE DE LIMA",
                "CLASE-VIAL": "CALLE",
                "NUM": "5",
                "DISTRITO": "LATINA",
                "BARRIO": "LAS AGUILAS",
                "CODIGO-POSTAL": "28024",
                "LATITUD": "40.38323792632855",
                "LONGITUD": "-3.783621006318095",
                "COORDENADA-X": "433485",
                "COORDENADA-Y": "4470588",
                "TIPO": "/contenido/entidadesYorganismos/AparcamientosPublicos",
            }
        )

        assert poi is not None
        self.assertEqual("parking:11483771", poi["id"])
        self.assertEqual("parking", poi["category"])
        self.assertEqual("madrid_parking_official", poi["source_id"])
        self.assertEqual("public", poi["tags"]["access_scope"])
        self.assertEqual("published_wgs84", poi["tags"]["coordinate_source"])
        self.assertEqual([], validation_errors("poi.schema.json", poi))

    def test_recupera_por_utm_la_longitud_malformada_de_la_fuente(self) -> None:
        poi = MODULE.normalise_record(
            {
                "PK": "36269",
                "NOMBRE": "Aparcamiento mixto. Encuentro",
                "LATITUD": "40.4058768185719",
                "LONGITUD": "--3.65138632197171",
                "COORDENADA-X": "444728",
                "COORDENADA-Y": "4473010",
                "TIPO": "/contenido/entidadesYorganismos/AparcamientosResidentes",
            }
        )

        assert poi is not None
        self.assertAlmostEqual(40.4058768, poi["lat"], delta=0.00002)
        self.assertAlmostEqual(-3.6513863, poi["lon"], delta=0.00002)
        self.assertEqual("derived_etrs89_utm30n", poi["tags"]["coordinate_source"])
        self.assertEqual("resident_or_mixed", poi["tags"]["access_scope"])
        self.assertNotIn("public_access", poi["tags"])

    def test_documento_es_determinista_y_explica_cada_descarte(self) -> None:
        records = [
            {
                "PK": "1",
                "NOMBRE": "Aparcamiento Plaza de España",
                "LATITUD": "40.423",
                "LONGITUD": "-3.711",
                "TIPO": "/AparcamientosPublicos",
            },
            {
                "PK": "1",
                "NOMBRE": "Duplicado",
                "LATITUD": "40.423",
                "LONGITUD": "-3.711",
            },
            {"PK": "", "LATITUD": "40.42", "LONGITUD": "-3.70"},
            {"PK": "sin-coordenadas"},
        ]
        raw = _csv_bytes(records)

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
        self.assertEqual({"published_wgs84": 1}, first["coordinate_counts"])
        self.assertEqual("CC-BY-4.0", first["license"])
        self.assertEqual(2, first["freshness_sla_days"])
        self.assertEqual(0.667, first["territorial_reuse_ratio"])
        self.assertTrue(first["schema_reused"])


class MadridParkingRetrievalTest(unittest.TestCase):
    def test_filtra_aparcamiento_publico_sin_confundir_mixto(self) -> None:
        from baseline import BaselineRetriever

        retriever = BaselineRetriever(
            {
                "parking": [
                    {
                        "id": "parking:resident",
                        "name": {"es": "Aparcamiento mixto"},
                        "lat": 40.415,
                        "lon": -3.707,
                        "tags": {"access_scope": "resident_or_mixed"},
                    },
                    {
                        "id": "parking:public",
                        "name": {"es": "Aparcamiento público"},
                        "lat": 40.420,
                        "lon": -3.710,
                        "tags": {"access_scope": "public"},
                    },
                ]
            }
        )
        results = retriever.retrieve(
            "aparcamiento público cerca de la Plaza Mayor",
            {"lat": 40.41551, "lon": -3.70740},
        )
        self.assertEqual(["parking:public"], [row["id"] for row in results])

    def test_consulta_multicapa_conjunta_devuelve_las_dos_capas(self) -> None:
        from baseline import BaselineRetriever

        retriever = BaselineRetriever(
            {
                "parking": [{"id": "parking:1", "name": {"es": "Parking"},
                             "lat": 40.42, "lon": -3.70, "tags": {}}],
                "bikepark": [{"id": "bikepark:1", "name": {"es": "Bici"},
                               "lat": 40.42, "lon": -3.70, "tags": {}}],
            }
        )
        results = retriever.retrieve(
            "parking y aparcabicis cerca de Sol",
            {"lat": 40.41693, "lon": -3.70355},
        )
        self.assertEqual({"parking:1", "bikepark:1"}, {row["id"] for row in results})


def _csv_bytes(records: list[dict]) -> bytes:
    fields = sorted({key for record in records for key in record})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue().encode("iso-8859-1")


if __name__ == "__main__":
    unittest.main()
