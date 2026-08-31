"""Serving simultáneo de Euskadi y Madrid a través del seam HTTP."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = ROOT / "service"
GEO_PACKAGE = ROOT.parent / "emap-next" / "packages" / "geo"
sys.path[:0] = [str(ROOT), str(SERVICE_DIR), str(ROOT / "evals"), str(GEO_PACKAGE)]

from regions import load_territory  # noqa: E402
from service.runtime import RuntimeRegistry  # noqa: E402


def _load_service():
    spec = importlib.util.spec_from_file_location(
        "emap_labs_multiterritory_service_test", SERVICE_DIR / "app.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Retriever:
    name = "fake-hybrid"
    sim_threshold = 0.8

    def __init__(self, place: str) -> None:
        self.place = place

    def detect_layers_with_scores(self, _query: str):
        return ["fountains"], {"fountains": 1.0}, "keywords"

    def retrieve(self, _query: str, _anchor: dict | None, k: int):
        return [
            {
                "id": f"fountains:{self.place}",
                "name": self.place,
                "lat": 40.4168,
                "lon": -3.7038,
                "layer": "fountains",
                "tags": {},
            }
        ][:k]


@dataclass(frozen=True)
class _Runtime:
    territory: object
    retriever: _Retriever
    documents: dict | None = None


def _request(app) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/search",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 123),
            "server": ("testserver", 80),
            "scheme": "http",
            "app": app,
        }
    )


class MultiTerritorySearchTest(unittest.TestCase):
    def test_busca_madrid_sin_usar_el_runtime_de_euskadi(self) -> None:
        service = _load_service()
        service.app.state.runtime_registry = RuntimeRegistry(
            {
                "euskadi": _Runtime(load_territory("euskadi"), _Retriever("Euskadi")),
                "madrid": _Runtime(load_territory("madrid"), _Retriever("Madrid")),
            }
        )
        service._rate_window.clear()
        service._log_query = lambda *_args, **_kwargs: None
        service.explain_result = lambda *_args, **_kwargs: {}
        service.explain_detection = lambda *_args, **_kwargs: {}
        service.poi_freshness = lambda *_args, **_kwargs: {}

        body = service.search(
            _request(service.app),
            q="fuente",
            territory="madrid",
            lat=40.4168,
            lon=-3.7038,
            k=1,
        )

        self.assertEqual("madrid", body["territory"])
        self.assertEqual("0.3.0", body["territory_version"])
        self.assertEqual("Madrid", body["results"][0]["name"])

    def test_error_explicito_sin_fallback_para_territorio_invalido(self) -> None:
        service = _load_service()
        service.app.state.runtime_registry = RuntimeRegistry(
            {
                "euskadi": _Runtime(
                    load_territory("euskadi"), _Retriever("Euskadi")
                ),
                "madrid": _Runtime(
                    load_territory("madrid"), _Retriever("Madrid")
                ),
            }
        )
        service._rate_window.clear()

        unknown = service.search(
            _request(service.app), q="fuente", territory="desconocido", k=1
        )
        missing = service.search(_request(service.app), q="fuente", k=1)

        self.assertEqual(404, unknown.status_code)
        self.assertEqual("unknown_territory", json.loads(unknown.body)["error"])
        self.assertEqual(422, missing.status_code)
        self.assertEqual("territory_required", json.loads(missing.body)["error"])

    def test_requests_alternadas_y_concurrentes_preservan_evidence(self) -> None:
        service = _load_service()
        today = date.today().isoformat()
        service.app.state.runtime_registry = RuntimeRegistry(
            {
                "euskadi": _Runtime(
                    load_territory("euskadi"),
                    _Retriever("Euskadi"),
                    {"fountains": _document("fuente-euskadi", today)},
                ),
                "madrid": _Runtime(
                    load_territory("madrid"),
                    _Retriever("Madrid"),
                    {"fountains": _document("fuente-madrid", today)},
                ),
            }
        )
        service._rate_window.clear()
        service._log_query = lambda *_args, **_kwargs: None

        def call(territory: str) -> tuple[str, str, str, str]:
            lat, lon = (
                (43.263, -2.935)
                if territory == "euskadi"
                else (40.4168, -3.7038)
            )
            body = service.search(
                _request(service.app),
                q="fuente",
                territory=territory,
                lat=lat,
                lon=lon,
                k=1,
            )
            result = body["results"][0]
            return (
                body["territory"],
                result["name"],
                result["why"]["source"],
                result["data"]["data_source"],
            )

        expected = {
            "euskadi": (
                "euskadi", "Euskadi", "fuente-euskadi", "fuente-euskadi"
            ),
            "madrid": (
                "madrid", "Madrid", "fuente-madrid", "fuente-madrid"
            ),
        }
        for territory in ("euskadi", "madrid", "euskadi", "madrid"):
            self.assertEqual(expected[territory], call(territory))

        territories = ("euskadi", "madrid") * 20
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(call, territories))
        self.assertEqual([expected[item] for item in territories], results)


def _document(source: str, source_updated: str) -> dict:
    return {
        "source": source,
        "license": "CC-BY-4.0",
        "source_updated": source_updated,
        "pois": [],
    }


if __name__ == "__main__":
    unittest.main()
