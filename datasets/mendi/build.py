#!/usr/bin/env python3
"""Cimas de Bizkaia desde OSM (Overpass) → POIs normalizados (vertical mendi).

Roadmap: "el monte en transporte público" — cimas y senderos homologados
cruzados con OTP. v0 de este pipeline: cimas (`natural=peak`) de Bizkaia
con nombre. Las rutas (GR/PR) llegarán en una iteración posterior.

Escribe emap-next/data/pois-euskadi/peaks.json (esquema pois estándar).

Uso: ../emap-next/.venv/bin/python datasets/mendi/build.py
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

LABS = Path(__file__).resolve().parents[2]
OUT = LABS / ".." / "emap-next" / "data" / "pois-euskadi" / "peaks.json"

OVERPASS = "https://overpass-api.de/api/interpreter"
# Bizkaia = ES-BI (admin_level 6). Solo nodos peak: las cimas son puntos.
QUERY = """
[out:json][timeout:180];
area["ISO3166-2"="ES-BI"][admin_level=6]->.bizkaia;
node["natural"="peak"](area.bizkaia);
out body;
"""


def fetch() -> list[dict]:
    req = urllib.request.Request(
        OVERPASS,
        data=("data=" + urllib.parse.quote(QUERY)).encode(),
        headers={"User-Agent": "emap-labs/mendi (contact: github.com/r3tr0eth/emap-labs)"},
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r)["elements"]


def main() -> None:
    elements = fetch()
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


if __name__ == "__main__":
    main()
