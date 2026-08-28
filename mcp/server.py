#!/usr/bin/env python3
"""emap-mcp — movilidad hiperlocal de Euskadi para agentes (roadmap L5).

No existe (research 2026-07-08) un MCP que exponga inteligencia de movilidad
hiperlocal: búsqueda semántica local bilingüe, explain-place, rutas
multimodales y "el monte en transporte público". Este servidor envuelve los
endpoints públicos de emap (API de solo lectura) — no duplica lógica.

Uso (stdio, p. ej. Claude Desktop):
    .venv/bin/python mcp/server.py

Config Claude Desktop:
    {"mcpServers": {"emap": {"command": "<repo>/.venv/bin/python",
                             "args": ["<repo>/mcp/server.py"]}}}

Remoto (streamable-http, tras nginx):
    EMAP_MCP_TRANSPORT=streamable-http EMAP_MCP_PORT=8084 python mcp/server.py

Principios heredados: NO SE FINGE (si la API no sabe, la herramienta dice
que no sabe), atribución SIEMPRE (ODbL/GTFS/CC-BY), infraestructura jamás
personas.
"""
from __future__ import annotations

import math
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

VERSION = "0.1.2"

# API pública de emap. Por defecto sigue el deploy actual en Vercel; cuando
# emapapp.com sea canónico de mapa/API se cambia con EMAP_API_URL (sin
# redeploy de código si se setea en systemd).
API = os.environ.get("EMAP_API_URL", "https://emap-next.vercel.app").rstrip("/")
# El planificador de montaña vive en emap-labs, no en la API serverless.
# Mantener ambas bases separadas evita inventar rutas proxy que no existen.
SEMANTIC_API = os.environ.get(
    "EMAP_SEMANTIC_URL", "https://vps.emapapp.com/semantic"
).rstrip("/")
# Marca en atribución (dominio de producto cuando exista; no es la URL del MCP).
SITE = os.environ.get("EMAP_SITE_URL", "https://emapapp.com").rstrip("/")
ATTRIBUTION = (
    f"emap ({SITE.replace('https://', '').replace('http://', '')}) · "
    "© OpenStreetMap (ODbL) + GTFS oficiales + Open Data Euskadi (CC-BY-4.0)"
)

# stdio (default, Claude Desktop local) o streamable-http (VPS, sin
# instalación local): EMAP_MCP_TRANSPORT=streamable-http + HOST/PORT.
TRANSPORT = os.environ.get("EMAP_MCP_TRANSPORT", "stdio")
BIND_HOST = os.environ.get("EMAP_MCP_HOST", "127.0.0.1")
BIND_PORT = int(os.environ.get("EMAP_MCP_PORT", "8084"))


def _split_csv(raw: str) -> list[str]:
    return [h.strip() for h in raw.split(",") if h.strip()]


def _default_allowed_hosts(port: int) -> str:
    """Local (con el puerto real) + personal (prod) + candidatos emapapp.

    La allowlist anti DNS-rebinding del SDK compara el header Host tal cual
    (incluye :puerto en llamadas directas). Tras nginx el Host es solo el
    dominio público.
    """
    local = [
        f"127.0.0.1:{port}",
        f"localhost:{port}",
        "127.0.0.1",
        "localhost",
    ]
    public = [
        "vps.emapapp.com",
        "emapapp.com",
        "mcp.emapapp.com",
        "www.emapapp.com",
    ]
    return ",".join(local + public)


mcp = FastMCP(
    "emap",
    website_url=SITE,
    host=BIND_HOST,
    port=BIND_PORT,
    transport_security=TransportSecuritySettings(
        allowed_hosts=_split_csv(
            os.environ.get(
                "EMAP_MCP_ALLOWED_HOSTS",
                _default_allowed_hosts(BIND_PORT),
            )
        ),
        allowed_origins=_split_csv(os.environ.get("EMAP_MCP_ALLOWED_ORIGINS", "")),
    ),
    instructions=(
        "Movilidad hiperlocal de Euskadi (País Vasco): transporte público "
        "multi-red, POIs urbanos, búsqueda semántica ES/EU y montañismo en "
        "transporte público. Euskadiko mugikortasun hiperlokala. Hyperlocal "
        "mobility for the Basque Country. Cita siempre la atribución que "
        "acompaña cada respuesta."
    ),
)

# capas de /api/pois/{layer} servidas hoy (públicas, ODbL/CC-BY)
POI_LAYERS = ("fountains", "toilets", "parking", "bikepark", "defib",
              "beaches", "ev", "cameras", "fuel", "peaks",
              "metro", "euskotren", "cercanias", "bilbobus", "bizkaibus")


def _hav_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * (1 - math.cos((lon2 - lon1) * p)) / 2)
    return 12742000 * math.asin(math.sqrt(a))


async def _get(path: str, **params: Any) -> dict:
    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get(f"{API}{path}", params=params)
        r.raise_for_status()
        return r.json()


def _out(payload: dict) -> dict:
    return {**payload, "attribution": ATTRIBUTION}


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> JSONResponse:
    """Liveness para nginx/systemd/monitores. Sin auth (público a propósito)."""
    return JSONResponse({
        "status": "ok",
        "service": "emap-mcp",
        "version": VERSION,
        "transport": TRANSPORT,
        "api": API,
        "semantic_api": SEMANTIC_API,
    })


@mcp.tool()
async def search_places(query: str, lat: float, lon: float, k: int = 5) -> dict:
    """Búsqueda semántica local en español o euskera ("dónde beber agua",
    "haurra aldatzeko lekua"). · Bilaketa semantikoa gaztelaniaz edo euskaraz.
    · Semantic local search in Spanish or Basque. Devuelve POIs cercanos al
    punto (lat, lon) o abstención honesta si no entiende la consulta."""
    d = await _get("/api/semantic-search", q=query, lat=lat, lon=lon, k=k)
    if d.get("unavailable"):
        return _out({"error": "servicio semántico no disponible ahora mismo"})
    fields = (
        "query", "abstained", "results", "territory", "territory_version",
        "retriever", "reranked", "explanation", "limitations",
    )
    payload = {key: d[key] for key in fields if key in d}
    payload.setdefault("query", query)
    payload.setdefault("abstained", False)
    payload.setdefault("results", [])
    return _out(payload)


@mcp.tool()
async def nearby_pois(layer: str, lat: float, lon: float, limit: int = 5) -> dict:
    """POIs más cercanos de una capa concreta. Capas: fountains (fuentes),
    toilets (aseos), parking, bikepark (aparcabicis), defib (DEA), beaches
    (playas), ev (cargadores), cameras, fuel (gasolineras), peaks (cimas),
    metro, euskotren, cercanias, bilbobus, bizkaibus. · Geruza bateko POI
    hurbilenak. · Nearest POIs of a given layer."""
    if layer not in POI_LAYERS:
        return _out({"error": f"capa desconocida; usa una de {POI_LAYERS}"})
    d = 0.03  # ~3 km de bbox; suficiente para "cerca de mí"
    doc = await _get(f"/api/pois/{layer}",
                     bbox=f"{lon-d:.4f},{lat-d:.4f},{lon+d:.4f},{lat+d:.4f}")
    pois = doc.get("pois", [])
    for p in pois:
        p["distance_m"] = int(_hav_m(lat, lon, p["lat"], p["lon"]))
    pois.sort(key=lambda p: p["distance_m"])
    return _out({"layer": layer, "results": pois[:max(1, min(limit, 20))]})


@mcp.tool()
async def explain_place(lat: float, lon: float) -> dict:
    """Contexto de un punto: barrio/municipio y servicios cercanos (rail,
    bus, aseos…) con distancias. · Puntu baten testuingurua: auzoa eta
    zerbitzu hurbilak. · What's around a point: neighborhood and nearby
    services with distances."""
    return _out(await _get("/api/explain-place", lat=lat, lon=lon))


@mcp.tool()
async def plan_route(from_lat: float, from_lon: float, to_lat: float,
                     to_lon: float, mode: str = "transit") -> dict:
    """Ruta real entre dos puntos con la infraestructura propia de emap
    (OSRM/OTP). mode: transit | walk | bike | car. · Bi punturen arteko
    ibilbidea. · Real route between two points. Devuelve duración,
    distancia y tramos (sin geometría completa)."""
    if mode not in ("transit", "walk", "bike", "car"):
        return _out({"error": "mode debe ser transit|walk|bike|car"})
    d = await _get("/api/route", mode=mode,
                   **{"from": f"{from_lat},{from_lon}", "to": f"{to_lat},{to_lon}"})
    if d.get("unavailable") or d.get("error"):
        return _out({"error": d.get("error") or "ruta no disponible para ese modo"})
    # Adapter deliberadamente estrecho: conserva el contrato estable y la
    # evidencia, pero no reenvía geometrías ni alternativas pesadas al agente.
    route_fields = (
        "version", "provider", "engine", "mode", "label", "duration",
        "distance", "origin", "destination", "summary", "operators",
        "fareSystems", "dataSources", "confidence", "limitations",
        "transfers", "start_time", "end_time", "recommendation", "zbe",
        "impact", "fare", "legs",
    )
    slim = {key: d[key] for key in route_fields if key in d}
    if "legs" in slim and isinstance(slim["legs"], list):
        leg_fields = (
            "mode", "instruction", "line", "from", "to", "duration",
            "distance", "start_time", "end_time", "agency", "stops",
            "headsign", "impact",
        )
        slim["legs"] = [
            {key: leg[key] for key in leg_fields if key in leg}
            for leg in slim["legs"]
        ]
    return _out(slim or d)


@mcp.tool()
async def plan_hike(lat: float, lon: float, max_stop_dist_m: int = 2000,
                    min_ele_m: int = 0, max_results: int = 5,
                    date: str | None = None,
                    start_time: str = "08:00") -> dict:
    """El monte en transporte público: cimas de Euskadi (2.825, OSM)
    alcanzables por transporte. Para cada candidata, planificación real con
    horarios GTFS: ida (transit+walk), tiempo de ascenso, regreso verificable.
    · Mendia garraio publikoz: tontor iritsgarriak planifikatuta.
    · Peak-bagging by public transport. Con horarios reales."""
    # Obtener candidatas (distancia linea recta como filtro inicial)
    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get(f"{API}/data/processed/mendi/peaks-transit.json")
        r.raise_for_status()
        cross = r.json()
    cands = [i for i in cross["items"]
             if i["nearest_stop"]["dist_m"] <= max_stop_dist_m
             and (i.get("ele") or 0) >= min_ele_m]
    for i in cands:
        i["dist_from_you_m"] = int(_hav_m(lat, lon, i["lat"], i["lon"]))
    cands.sort(key=lambda i: i["dist_from_you_m"])
    top = cands[:max(1, min(max_results, 20))]

    # Planificar cada candidata con el motor de horarios reales
    planned = []
    async with httpx.AsyncClient(timeout=30) as c:
        for cand in top:
            peak_name = cand["peak"]["es"]
            try:
                resp = await c.get(
                    f"{SEMANTIC_API}/hike-plan",
                    params={"peak": peak_name, "from_lat": lat,
                            "from_lon": lon, "date": date or "",
                            "start_time": start_time},
                    timeout=25,
                )
                resp.raise_for_status()
                plan = resp.json()
                planned.append(plan)
            except (httpx.HTTPError, ValueError):
                planned.append({
                    "ok": False,
                    "peak": cand["peak"],
                    "reason": "planificador de montaña no disponible",
                })

    return _out({
        "method": "otp-transit-walk + gtfs-schedules",
        "hike_plans": planned,
        "hint": ("Los horarios son orientativos. Verifica con la operadora "
                 "antes de salir."),
    })


if __name__ == "__main__":
    mcp.run(transport=TRANSPORT)
