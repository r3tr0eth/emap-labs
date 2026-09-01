"""Regresiones del contrato público del servicio semántico."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = ROOT / "service"
GEO_PACKAGE = ROOT.parent / "emap-next" / "packages" / "geo"
sys.path[:0] = [str(SERVICE_DIR), str(GEO_PACKAGE)]


def _load_service():
    spec = importlib.util.spec_from_file_location(
        "emap_labs_service_contract_test", SERVICE_DIR / "app.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeRetriever:
    name = "hybrid-minilm"
    sim_threshold = 0.5

    def __init__(self) -> None:
        self.requested_k: list[int] = []

    def detect_layers_with_scores(self, _query: str):
        return ["fountains"], {"fountains": 0.91}, "semantic"

    def retrieve(self, _query: str, _anchor: dict | None, k: int):
        self.requested_k.append(k)
        return [
            {
                "id": f"fountains:{idx}",
                "name": f"Fuente {idx}",
                "lat": 43.26 + idx / 1000,
                "lon": -2.93,
                "layer": "fountains",
                "tags": {},
            }
            for idx in range(k)
        ]


class SearchContractTest(unittest.TestCase):
    def test_no_declara_reranking_cuando_no_existe(self) -> None:
        service = _load_service()
        retriever = _FakeRetriever()
        service.app.state.runtime_registry = service.RuntimeRegistry(
            {
                "euskadi": SimpleNamespace(
                    territory=service.load_territory("euskadi"),
                    retriever=retriever,
                    documents={},
                )
            }
        )
        service._rate_window.clear()
        service._log_query = lambda *_args: None
        service.explain_result = lambda *_args, **_kwargs: {}
        service.explain_detection = lambda *_args: {}
        service.poi_freshness = lambda *_args, **_kwargs: {}

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/search",
                "headers": [],
                "query_string": b"",
                "client": ("testclient", 123),
                "server": ("testserver", 80),
                "scheme": "http",
                "app": service.app,
            }
        )
        body = service.search(
            request, q="donde beber agua", territory="euskadi", k=2
        )

        self.assertEqual("hybrid-minilm", body["retriever"])
        self.assertFalse(body["reranked"])
        self.assertEqual("euskadi", body["territory"])
        self.assertEqual("0.2.0", body["territory_version"])
        self.assertEqual([2], retriever.requested_k)
        self.assertEqual(2, len(body["results"]))


class MetricsContractTest(unittest.TestCase):
    def test_metricas_distinguen_no_result_abstencion_y_unsupported(self) -> None:
        service = _load_service()  # módulo fresco: contadores a cero
        service._metric("euskadi", "hybrid", 5, "NO_RESULT")
        service._metric("euskadi", "hybrid", 5, "ABSTAINED")
        service._metric("madrid", "hybrid", 5, "UNSUPPORTED",
                        stale_count=2, source_failures=1)
        service._metric("madrid", "geo-nearest", 5, "ANSWERED")

        self.assertEqual(1, service._METRICS["no_result"])
        self.assertEqual(1, service._METRICS["abstained"])
        self.assertEqual(1, service._METRICS["unsupported"])
        self.assertEqual(1, service._METRICS["source_failure"])
        self.assertEqual(2, service._METRICS["stale_source"])
        self.assertEqual(4, service._METRICS["request_count"])
        self.assertEqual({"euskadi": 2, "madrid": 2},
                         service._METRICS["by_territory"])


class FreshnessSlaTest(unittest.TestCase):
    def test_fallback_de_sla_por_territorio_es_neutro(self) -> None:
        import data_freshness as df

        # BASE nunca absorbe los overrides del territorio del proceso…
        self.assertEqual(180, df.BASE_SLA_DAYS["parking"])
        # …que solo viven en DEFAULT (vía legacy con EMAP_TERRITORY).
        for layer, sla in df.TERRITORY.freshness_sla_days.items():
            self.assertEqual(sla, df.DEFAULT_SLA_DAYS[layer])

        report = df.quality_report_from_documents(
            {"parking": {"source_updated": "2025-01-01", "source": "x"}},
            sla_by_layer={},
        )
        row = report["layers"][0]
        self.assertEqual(180, row["sla_days"])
        self.assertEqual("stale", row["status"])

    def test_fallback_de_sla_respeta_la_base_por_capa(self) -> None:
        # Regresión: /search y /nearby pasan sla_days=None cuando el territorio
        # no declara override; debe aplicar el SLA por capa de BASE (cameras
        # 30, peaks 365), nunca un 180 plano.
        import data_freshness as df
        from datetime import date, timedelta

        hace_45 = (date.today() - timedelta(days=45)).isoformat()
        hace_200 = (date.today() - timedelta(days=200)).isoformat()

        cameras = df.poi_freshness(
            {"layer": "cameras"}, document={"source_updated": hace_45}
        )
        self.assertEqual("stale", cameras["freshness"])  # 45 > SLA 30

        peaks = df.poi_freshness(
            {"layer": "peaks"}, document={"source_updated": hace_200}
        )
        self.assertEqual("fresh", peaks["freshness"])  # 200 < SLA 365


if __name__ == "__main__":
    unittest.main()
