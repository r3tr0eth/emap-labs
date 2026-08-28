"""Regresiones del contrato público del servicio semántico."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

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
        service._retriever = retriever
        service._rate_window.clear()
        service._log_query = lambda *_args: None
        service.explain_result = lambda *_args: {}
        service.explain_detection = lambda *_args: {}
        service.poi_freshness = lambda *_args: {}

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
            }
        )
        body = service.search(request, q="donde beber agua", k=2)

        self.assertEqual("hybrid-minilm", body["retriever"])
        self.assertFalse(body["reranked"])
        self.assertEqual("euskadi", body["territory"])
        self.assertEqual("0.2.0", body["territory_version"])
        self.assertEqual([2], retriever.requested_k)
        self.assertEqual(2, len(body["results"]))


if __name__ == "__main__":
    unittest.main()
