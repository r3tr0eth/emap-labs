"""Regresiones de los adapters que publica EMAP por MCP."""

from __future__ import annotations

import asyncio
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]


def _load_server():
    spec = importlib.util.spec_from_file_location(
        "emap_mcp_contract_test", ROOT / "mcp" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    urls: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str, **kwargs):
        self.urls.append(url)
        if url.endswith("/data/processed/mendi/peaks-transit.json"):
            return _FakeResponse(
                {
                    "items": [
                        {
                            "nearest_stop": {"dist_m": 300},
                            "ele": 650,
                            "lat": 43.18,
                            "lon": -2.87,
                            "peak": {"es": "Cima de prueba", "eu": "Proba tontorra"},
                        }
                    ]
                }
            )
        return _FakeResponse({"ok": True, "peak": "Cima de prueba"})


class McpContractTest(unittest.TestCase):
    def test_search_places_conserva_contexto_territorial_y_metodo(self) -> None:
        server = _load_server()
        server._get = AsyncMock(
            return_value={
                "query": "donde beber agua",
                "abstained": False,
                "results": [{"id": "fountains:1", "layer": "fountains"}],
                "territory": "euskadi",
                "territory_version": "0.2.0",
                "retriever": "hybrid-keywords-then-minilm",
                "reranked": False,
                "explanation": {"method": "keywords"},
                "attribution": "Ayuntamiento de Madrid (CC BY 4.0)",
            }
        )

        body = asyncio.run(server.search_places("donde beber agua", 43.26, -2.93))

        self.assertEqual("euskadi", body["territory"])
        self.assertEqual("0.2.0", body["territory_version"])
        self.assertEqual("hybrid-keywords-then-minilm", body["retriever"])
        self.assertFalse(body["reranked"])
        self.assertEqual(
            "Ayuntamiento de Madrid (CC BY 4.0)", body["attribution"]
        )

    def test_out_solo_usa_atribucion_global_como_fallback(self) -> None:
        server = _load_server()

        self.assertEqual(server.ATTRIBUTION, server._out({})["attribution"])
        self.assertEqual(
            "Fuente territorial",
            server._out({"attribution": "Fuente territorial"})["attribution"],
        )

    def test_plan_route_conserva_metricas_del_contrato_api(self) -> None:
        server = _load_server()
        route = {
            "version": "1.0",
            "provider": "osrm",
            "engine": "osrm",
            "mode": "car",
            "duration": 612.3,
            "distance": 7074.1,
            "summary": "Ruta de prueba",
            "legs": [
                {
                    "mode": "car",
                    "from": "A",
                    "to": "B",
                    "duration": 612.3,
                    "distance": 7074.1,
                }
            ],
            "dataSources": ["osrm"],
            "confidence": {"level": "high"},
            "limitations": [],
        }
        server._get = AsyncMock(return_value=route)

        body = asyncio.run(server.plan_route(43.30, -2.91, 43.26, -2.93))

        self.assertEqual(612.3, body["duration"])
        self.assertEqual(7074.1, body["distance"])
        self.assertEqual(612.3, body["legs"][0]["duration"])
        self.assertEqual(7074.1, body["legs"][0]["distance"])
        self.assertEqual("osrm", body["provider"])

    def test_plan_hike_usa_el_servicio_semantico_configurado(self) -> None:
        server = _load_server()
        _FakeAsyncClient.urls = []
        server.API = "https://api.example"

        with patch.object(server, "SEMANTIC_API", "https://semantic.example", create=True), patch.object(
            server.httpx, "AsyncClient", _FakeAsyncClient
        ):
            body = asyncio.run(server.plan_hike(43.26, -2.93, max_results=1))

        self.assertIn("https://semantic.example/hike-plan", _FakeAsyncClient.urls)
        self.assertNotIn("https://api.example/semantic/hike-plan", _FakeAsyncClient.urls)
        self.assertTrue(body["hike_plans"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
