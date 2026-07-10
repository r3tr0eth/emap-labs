#!/usr/bin/env python3
"""emap-mcp — movilidad hiperlocal de Euskadi para agentes (roadmap L5).

No existe (research 2026-07-08) un MCP que exponga inteligencia de movilidad
hiperlocal: búsqueda semántica local bilingüe, explain-place, rutas
multimodales y "el monte en transporte público". Este servidor envuelve los
endpoints públicos de emap (emap-next.vercel.app) — no duplica lógica.

Uso (stdio, p. ej. Claude Desktop):
    .venv/bin/python mcp/server.py

Config Claude Desktop:
    {"mcpServers": {"emap": {"command": "<repo>/.venv/bin/python",
                             "args": ["<repo>/mcp/server.py"]}}}

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

API = os.environ.get("EMAP_API_URL", "https://emap-next.vercel.app")
ATTRIBUTION = ("emap (emap-next.vercel.app) · © OpenStreetMap (ODbL) + "
               "GTFS oficiales + Open Data Euskadi (CC-BY-4.0)")

# stdio (default, Claude Desktop local) o streamable-http (VPS, sin
# instalación local): EMAP_MCP_TRANSPORT=streamable-http + HOST/PORT.
TRANSPORT = os.environ.get("EMAP_MCP_TRANSPORT", "stdio")

mcp = FastMCP(
    "emap",
    host=os.environ.get("EMAP_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("EMAP_MCP_PORT", "8084")),
    # tras nginx el Host es el dominio público: hay que permitirlo (la
    # protección anti DNS-rebinding del SDK responde 421 si no)
    transport_security=TransportSecuritySettings(
        allowed_hosts=[h for h in os.environ.get(
            "EMAP_MCP_ALLOWED_HOSTS",
            "127.0.0.1:8084,localhost:8084").split(",") if h],
        allowed_origins=[],
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


@mcp.tool()
async def search_places(query: str, lat: float, lon: float, k: int = 5) -> dict:
    """Búsqueda semántica local en español o euskera ("dónde beber agua",
    "haurra aldatzeko lekua"). · Bilaketa semantikoa gaztelaniaz edo euskaraz.
    · Semantic local search in Spanish or Basque. Devuelve POIs cercanos al
    punto (lat, lon) o abstención honesta si no entiende la consulta."""
    d = await _get("/api/semantic-search", q=query, lat=lat, lon=lon, k=k)
    if d.get("unavailable"):
        return _out({"error": "servicio semántico no disponible ahora mismo"})
    return _out({"query": query, "abstained": d.get("abstained", False),
                 "results": d.get("results", [])})


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
    slim = {k: d[k] for k in ("mode", "duration_s", "distance_m", "legs",
                              "summary", "fare") if k in d}
    if "legs" in slim and isinstance(slim["legs"], list):
        slim["legs"] = [{k: l[k] for k in ("mode", "line", "from", "to",
                                           "duration_s", "distance_m",
                                           "headsign") if k in l}
                        for l in slim["legs"]]
    return _out(slim or d)


@mcp.tool()
async def plan_hike(lat: float, lon: float, max_stop_dist_m: int = 2000,
                    min_ele_m: int = 0, max_results: int = 5) -> dict:
    """El monte en transporte público: cimas de Euskadi (2.825, OSM)
    alcanzables por transporte — para cada candidata, su parada/estación
    más cercana entre 9 redes. · Mendia garraio publikoz: tontor
    iritsgarriak. · Peak-bagging by public transport. HONESTO: distancias
    en línea recta, no ruta a pie; usa plan_route hasta la parada para el
    trayecto real."""
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
    return _out({
        "method": cross.get("method"),
        "candidates": cands[:max(1, min(max_results, 20))],
        "hint": ("usa plan_route(mode='transit') hasta la parada de la "
                 "candidata para el cómo-llegar real"),
    })


if __name__ == "__main__":
    mcp.run(transport=TRANSPORT)
