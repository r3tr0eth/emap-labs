import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path


def _load_server():
    # El repo contiene `mcp/server.py`, que debe cargarse sin sombrear el
    # paquete MCP externo durante la colección de tests.
    root = str(Path(__file__).resolve().parents[1])
    old = list(sys.path)
    sys.path[:] = [p for p in sys.path if p not in ("", root)]
    try:
        spec = importlib.util.spec_from_file_location("emap_mcp_server_test", Path(root) / "mcp/server.py")
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        try:
            spec.loader.exec_module(module)
        except ModuleNotFoundError as exc:
            raise unittest.SkipTest(f"MCP runtime no instalado en este entorno: {exc}")
        return module
    finally:
        sys.path[:] = old


class MCPContractTest(unittest.TestCase):
  def test_nearby_always_uses_intelligence_contract(self):
    server = _load_server()
    seen = {}

    async def fake_get(path, **params):
        seen["path"] = path
        seen["params"] = params
        return {"schema_version": "intelligence.response.v1", "territory": "madrid"}

    original = server._get
    server._get = fake_get
    try:
      response = asyncio.run(server.nearby_pois("parking", 40.4, -3.7))
    finally:
      server._get = original
    self.assertEqual(seen["path"], "/api/intelligence/nearby")
    self.assertNotIn("territory", seen["params"])
    self.assertEqual(response["schema_version"], "intelligence.response.v1")

  def test_search_places_forwards_territory_and_response_contract(self):
    server = _load_server()
    seen = {}

    async def fake_get(path, **params):
        seen["path"] = path
        seen["params"] = params
        return {
            "schema_version": "intelligence.response.v1",
            "answerable": True,
            "territory": "madrid",
            "territory_version": "0.3.0",
            "result": {"items": []},
            "evidence": [],
            "freshness": {"status": "fresh"},
            "confidence": {"level": "high", "score": 1.0},
            "retrieval_method": "hybrid",
        }

    original = server._get
    server._get = fake_get
    try:
      response = asyncio.run(server.search_places("parking", 40.4, -3.7, territory="madrid"))
    finally:
      server._get = original
    self.assertEqual(seen["path"], "/api/semantic-search")
    self.assertEqual(seen["params"]["territory"], "madrid")
    self.assertEqual(response["territory_version"], "0.3.0")
    self.assertEqual(response["schema_version"], "intelligence.response.v1")
