#!/usr/bin/env python3
"""Smoke test de emap-mcp (health + protocolo MCP + tools opcionales).

Uso:
  # local (levanta el servidor aparte en :8084, o usa --start)
  .venv/bin/python mcp/smoke.py
  .venv/bin/python mcp/smoke.py --base http://127.0.0.1:8084

  # prod actual (dominio personal)
  .venv/bin/python mcp/smoke.py --base https://vps.emapapp.com

  # futuro dominio de producto
  .venv/bin/python mcp/smoke.py --base https://mcp.emapapp.com

  # con tool real (San Mamés bikepark — criterio L5.1)
  .venv/bin/python mcp/smoke.py --base https://vps.emapapp.com --live

Salida: exit 0 si pasa; mensajes en stderr si falla.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

import httpx

EXPECTED_TOOLS = {
    "search_places",
    "nearby_pois",
    "explain_place",
    "plan_route",
    "plan_hike",
}

# San Mamés (criterio de aceptación L5.1 del roadmap)
SAN_MAMES = {"lat": 43.2644, "lon": -2.9494}


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"ok  {msg}")


def _mcp_headers(session_id: str | None = None) -> dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


def _parse_rpc_body(text: str) -> dict[str, Any]:
    """Acepta JSON puro o SSE (`event: message\\ndata: {...}`)."""
    text = text.strip()
    if not text:
        return {}
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                return json.loads(payload)
    # último recurso: primer objeto JSON embebido
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"cuerpo MCP no parseable: {text[:200]!r}")


def _mcp_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/mcp"):
        return base
    return f"{base}/mcp"


def _health_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/mcp"):
        base = base[: -len("/mcp")]
    return f"{base}/health"


def check_health(client: httpx.Client, base: str) -> bool:
    """Health es opcional en prod si nginx no lo expone aún. True si pasó."""
    url = _health_url(base)
    try:
        r = client.get(url, timeout=10)
    except httpx.HTTPError as e:
        _ok(f"health saltado ({url}: {e})")
        return False
    if r.status_code == 404:
        _ok(f"health no expuesto en {url} (normal si nginx solo proxea /mcp)")
        return False
    if r.status_code != 200:
        _fail(f"health {url} → HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status") != "ok" or data.get("service") != "emap-mcp":
        _fail(f"health payload inesperado: {data}")
    _ok(f"health {data.get('version', '?')} @ {url}")
    return True


def mcp_initialize(client: httpx.Client, mcp_url: str) -> str:
    r = client.post(
        mcp_url,
        headers=_mcp_headers(),
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "emap-mcp-smoke", "version": "0.1.2"},
            },
        },
        timeout=20,
    )
    if r.status_code != 200:
        _fail(f"initialize HTTP {r.status_code}: {r.text[:300]}")
    sid = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
    if not sid:
        _fail("initialize sin Mcp-Session-Id")
    body = _parse_rpc_body(r.text)
    if "result" not in body:
        _fail(f"initialize sin result: {body}")
    name = body["result"].get("serverInfo", {}).get("name")
    if name != "emap":
        _fail(f"serverInfo.name={name!r}, esperado 'emap'")
    _ok(f"initialize session={sid[:12]}…")
    # handshake
    client.post(
        mcp_url,
        headers=_mcp_headers(sid),
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        timeout=10,
    )
    return sid


def mcp_tools_list(client: httpx.Client, mcp_url: str, sid: str) -> None:
    r = client.post(
        mcp_url,
        headers=_mcp_headers(sid),
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        timeout=20,
    )
    if r.status_code != 200:
        _fail(f"tools/list HTTP {r.status_code}: {r.text[:300]}")
    body = _parse_rpc_body(r.text)
    tools = body.get("result", {}).get("tools") or []
    names = {t.get("name") for t in tools if isinstance(t, dict)}
    missing = EXPECTED_TOOLS - names
    if missing:
        _fail(f"tools faltantes: {sorted(missing)}; vi {sorted(names)}")
    _ok(f"tools/list ({len(names)}): {', '.join(sorted(names))}")


def mcp_live_nearby(client: httpx.Client, mcp_url: str, sid: str) -> None:
    """Criterio L5.1: bikepark cerca de San Mamés devuelve resultados."""
    r = client.post(
        mcp_url,
        headers=_mcp_headers(sid),
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "nearby_pois",
                "arguments": {
                    "layer": "bikepark",
                    "lat": SAN_MAMES["lat"],
                    "lon": SAN_MAMES["lon"],
                    "limit": 3,
                },
            },
        },
        timeout=40,
    )
    if r.status_code != 200:
        _fail(f"tools/call nearby_pois HTTP {r.status_code}: {r.text[:300]}")
    body = _parse_rpc_body(r.text)
    result = body.get("result") or {}
    # FastMCP suele devolver content[{type:text, text: json}]
    text_blob = ""
    if isinstance(result.get("content"), list):
        for part in result["content"]:
            if isinstance(part, dict) and part.get("type") == "text":
                text_blob += part.get("text") or ""
    elif isinstance(result, dict):
        text_blob = json.dumps(result)
    if "error" in text_blob and "results" not in text_blob:
        _fail(f"nearby_pois error: {text_blob[:400]}")
    try:
        payload = json.loads(text_blob)
    except json.JSONDecodeError:
        payload = result.get("structuredContent") or result.get("structured_content") or {}
    required = {"schema_version", "territory", "evidence", "freshness", "confidence"}
    missing_contract = sorted(key for key in required if key not in payload)
    if missing_contract:
        _fail(f"nearby_pois contrato incompleto; faltan {missing_contract}: {text_blob[:400]}")
    if payload.get("schema_version") != "intelligence.response.v1":
        _fail(f"nearby_pois schema inesperado: {payload.get('schema_version')!r}")
    if "attribution" not in text_blob and "OpenStreetMap" not in text_blob:
        # intentar parsear structuredContent
        sc = result.get("structuredContent") or result.get("structured_content")
        if not (isinstance(sc, dict) and sc.get("attribution")):
            _fail(f"nearby_pois sin attribution: {text_blob[:400]}")
    _ok("tools/call nearby_pois(bikepark, San Mamés) con contrato y atribución")


def main() -> None:
    p = argparse.ArgumentParser(description="Smoke test emap-mcp")
    p.add_argument(
        "--base",
        default="http://127.0.0.1:8084",
        help="Base del servicio (sin /mcp) o URL completa …/mcp",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Llama nearby_pois real (criterio L5.1 San Mamés)",
    )
    args = p.parse_args()
    base = args.base.rstrip("/")
    mcp_url = _mcp_url(base)

    print(f"→ smoke emap-mcp  base={base}  mcp={mcp_url}")
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        check_health(client, base)
        sid = mcp_initialize(client, mcp_url)
        mcp_tools_list(client, mcp_url, sid)
        if args.live:
            mcp_live_nearby(client, mcp_url, sid)
    print("SMOKE OK")


if __name__ == "__main__":
    main()
