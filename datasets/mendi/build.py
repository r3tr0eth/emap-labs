#!/usr/bin/env python3
"""Cimas y rutas de Bizkaia desde OSM (Overpass) — vertical mendi.

Roadmap: "el monte en transporte público" — cimas y senderos homologados
cruzados con transporte. Este pipeline produce las capas fuente:

  emap-next/data/pois-euskadi/peaks.json    cimas natural=peak con nombre
  emap-next/data/pois-euskadi/routes.json   rutas route=hiking (solo
                                            metadatos; geometría pendiente)

Uso: ../emap-next/.venv/bin/python datasets/mendi/build.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date
from pathlib import Path

LABS = Path(__file__).resolve().parents[2]
DATA = LABS / ".." / "emap-next" / "data" / "pois-euskadi"
OUT = DATA / "peaks.json"
OUT_ROUTES = DATA / "routes.json"

OVERPASS = "https://overpass-api.de/api/interpreter"
# Bizkaia = ES-BI (admin_level 6). Solo nodos peak: las cimas son puntos.
QUERY = """
[out:json][timeout:180];
area["ISO3166-2"="ES-BI"][admin_level=6]->.bizkaia;
node["natural"="peak"](area.bizkaia);
out body;
"""
# Rutas señalizadas de senderismo (relaciones). Solo tags en v1: la
# geometría (miembros way) pesa mucho y llegará cuando la capa la pida.
QUERY_ROUTES = """
[out:json][timeout:180];
area["ISO3166-2"="ES-BI"][admin_level=6]->.bizkaia;
relation["route"="hiking"](area.bizkaia);
out tags;
"""


ENDPOINTS = [OVERPASS, "https://overpass.kumi.systems/api/interpreter"]


def fetch(query: str) -> list[dict]:
    last: Exception | None = None
    for attempt in range(4):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        req = urllib.request.Request(
            url,
            data=("data=" + urllib.parse.quote(query)).encode(),
            headers={"User-Agent": "emap-labs/mendi (contact: github.com/r3tr0eth/emap-labs)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)["elements"]
        except Exception as e:  # 504/429 del endpoint público: esperar y rotar
            last = e
            print(f"  overpass KO ({url.split('/')[2]}: {e}) — reintento en 30s")
            time.sleep(30)
    raise SystemExit(f"Overpass agotado tras 4 intentos: {last}")


def build_routes() -> None:
    rels = fetch(QUERY_ROUTES)
    routes = []
    for el in rels:
        t = el.get("tags", {})
        if not (t.get("name") or t.get("ref")):
            continue  # sin nombre ni ref no hay ruta citable
        routes.append({
            "osm_id": el["id"],
            "name": t.get("name", ""),
            "ref": t.get("ref", ""),
            "network": t.get("network", ""),  # iwn/nwn/rwn/lwn
            "distance": t.get("distance", ""),
            "operator": t.get("operator", ""),
            "from": t.get("from", ""),
            "to": t.get("to", ""),
        })
    routes.sort(key=lambda r: (r["network"], r["ref"], r["name"]))
    OUT_ROUTES.write_text(json.dumps({
        "generated": date.today().isoformat(),
        "source": "OpenStreetMap (Overpass, relation route=hiking, área ES-BI)",
        "license": "ODbL 1.0 © OpenStreetMap contributors",
        "count": len(routes),
        "notes": ("solo metadatos de relaciones con name o ref; SIN geometría "
                  "(pendiente — los osm_id permiten traerla después); "
                  "cobertura según mapeo OSM"),
        "routes": routes,
    }, ensure_ascii=False))
    by_net = {}
    for r in routes:
        by_net[r["network"] or "?"] = by_net.get(r["network"] or "?", 0) + 1
    print(f"→ {OUT_ROUTES.resolve()}")
    print(f"rutas señalizadas: {len(routes)} · por red: {by_net}")


def main() -> None:
    elements = fetch(QUERY)
    named, unnamed = [], 0
    for el in elements:
        t = el.get("tags", {})
        name = t.get("name")
        if not name:
            unnamed += 1
            continue
        tags = {}
        ele = t.get("ele", "").replace(",", ".")
        try:
            tags["ele"] = round(float(ele), 1)
        except ValueError:
            pass  # sin elevación válida: se omite el tag, no se inventa
        for k in ("prominence", "wikidata", "summit:cross", "summit:register"):
            if t.get(k):
                tags[k] = t[k]
        named.append({
            "id": f"peak:{el['id']}",  # id del nodo OSM: estable y trazable
            "name": {"es": t.get("name:es", name), "eu": t.get("name:eu", name)},
            "lat": el["lat"], "lon": el["lon"], "tags": tags,
        })
    named.sort(key=lambda p: -p["tags"].get("ele", 0))

    OUT.write_text(json.dumps({
        "generated": date.today().isoformat(),
        "source": "OpenStreetMap (Overpass, natural=peak, área ES-BI)",
        "license": "ODbL 1.0 © OpenStreetMap contributors",
        "count": len(named),
        "notes": (f"solo cimas CON nombre ({unnamed} sin nombre omitidas); "
                  "cobertura según densidad de mapeo OSM"),
        "pois": named,
    }, ensure_ascii=False))
    with_ele = sum(1 for p in named if "ele" in p["tags"])
    print(f"→ {OUT.resolve()}")
    print(f"cimas con nombre: {len(named)} ({with_ele} con elevación; "
          f"{unnamed} sin nombre omitidas)")
    print("top 5:", ", ".join(
        f"{p['name']['es']} ({p['tags'].get('ele', '?')}m)" for p in named[:5]))
    build_routes()


if __name__ == "__main__":
    main()
