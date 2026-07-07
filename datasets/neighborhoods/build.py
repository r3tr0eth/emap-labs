#!/usr/bin/env python3
"""Barrios y municipios de Bizkaia (roadmap L0.2) → emap-next/data/processed/.

Fuente: OSM (Overpass), límites administrativos de Bizkaia:
  admin_level 8 = municipios · 9 = distritos (Bilbao) · 10 = barrios.

Cobertura honesta: municipios y distritos completos; barrios solo los
mapeados en OSM (~26 de los 34 oficiales de Bilbao a 2026-07). El upgrade
es la cartografía oficial (Bilbao Open Data / geoEuskadi) cuando publiquen
GeoJSON con licencia clara; mientras, mejorar OSM mejora nuestra base.

Ejecutar con el venv de emap-next (usa emap_geo para el parentesco):
    ../emap-next/.venv/bin/python datasets/neighborhoods/build.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from emap_geo.polygon import point_in_polygon

LABS_ROOT = Path(__file__).resolve().parents[2]
OUT = LABS_ROOT.parent / "emap-next" / "data" / "processed" / "neighborhoods"

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
QUERY = """
[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="6"]["name"="Bizkaia"]->.a;
rel(area.a)["boundary"="administrative"]["admin_level"~"^(8|9|10)$"];
out geom;
"""
KIND = {"8": "municipality", "9": "district", "10": "neighborhood"}
PRECISION = 5          # ~1 m
DP_TOLERANCE = 1e-4    # Douglas-Peucker en grados, ~8-11 m


def fetch() -> dict:
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last: Exception | None = None
    for url in MIRRORS:
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"User-Agent": "emap-labs/0.1"})
            with urllib.request.urlopen(req, timeout=240) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001 — probar el siguiente mirror
            last = exc
            print(f"  mirror caído {url}: {exc}", file=sys.stderr)
    raise SystemExit(f"todos los mirrors fallaron: {last}")


def stitch_rings(segments: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Une ways (role=outer o inner) en anillos cerrados casando extremos."""
    rings: list[list[tuple[float, float]]] = []
    pending = [s for s in segments if len(s) >= 2]
    while pending:
        ring = list(pending.pop(0))
        grew = True
        while grew and ring[0] != ring[-1]:
            grew = False
            for i, seg in enumerate(pending):
                if seg[0] == ring[-1]:
                    ring.extend(seg[1:])
                elif seg[-1] == ring[-1]:
                    ring.extend(reversed(seg[:-1]))
                elif seg[-1] == ring[0]:
                    ring[:0] = seg[:-1]
                elif seg[0] == ring[0]:
                    ring[:0] = reversed(seg[1:])
                else:
                    continue
                pending.pop(i)
                grew = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
    return rings


def simplify(ring: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Douglas-Peucker iterativo sobre (lat, lon) en grados."""
    if len(ring) <= 4:
        return ring
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        (y1, x1), (y2, x2) = ring[lo], ring[hi]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        worst, worst_i = 0.0, -1
        for i in range(lo + 1, hi):
            y, x = ring[i]
            d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
            if d > worst:
                worst, worst_i = d, i
        if worst > tol:
            keep[worst_i] = True
            stack.extend([(lo, worst_i), (worst_i, hi)])
    out = [p for p, k in zip(ring, keep) if k]
    return out if len(out) >= 4 else ring


def to_feature(rel: dict) -> dict | None:
    tags = rel.get("tags", {})
    outers, inners = [], []
    for m in rel.get("members", []):
        if m.get("type") != "way" or "geometry" not in m:
            continue
        seg = [(pt["lat"], pt["lon"]) for pt in m["geometry"]]
        (outers if m.get("role") in ("outer", "") else inners).append(seg)
    rings = stitch_rings(outers)
    if not rings:
        print(f"  descartado (sin anillo cerrado): {tags.get('name')}", file=sys.stderr)
        return None
    holes = stitch_rings(inners)

    def clean(r):
        r = simplify(r, DP_TOLERANCE)
        return [[round(lon, PRECISION), round(lat, PRECISION)] for lat, lon in r]

    # GeoJSON: MultiPolygon [[outer, hole...], ...]; los holes van con el
    # primer outer (suficiente para agregación; no hacemos containment fino)
    polygons = [[clean(r)] for r in sorted(rings, key=len, reverse=True)]
    polygons[0].extend(clean(h) for h in holes)

    # `name` es el nombre oficial sobre el terreno; name:es trae exónimos
    # arcaicos (Achuri, Indauchu) que ningún usuario local escribe.
    name = tags.get("name", "")
    props = {
        "id": f"osm:rel:{rel['id']}",
        "kind": KIND[tags["admin_level"]],
        "admin_level": int(tags["admin_level"]),
        "name": {"es": name, "eu": tags.get("name:eu", name)},
    }
    for src, dst in (("ine:municipio", "ine"), ("wikidata", "wikidata"),
                     ("population", "population")):
        if tags.get(src):
            props[dst] = tags[src]
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "MultiPolygon", "coordinates": polygons}}


def main() -> None:
    print("descargando límites administrativos de Bizkaia (OSM)…")
    raw = fetch()
    feats = [f for rel in raw["elements"] if (f := to_feature(rel))]
    feats.sort(key=lambda f: (f["properties"]["admin_level"],
                              f["properties"]["name"]["es"]))

    # el filtro de área de Overpass cuela relaciones limítrofes de otras
    # provincias (Mondragón/Gipuzkoa, Zuya/Araba): Bizkaia = INE 48xxx
    munis = [f for f in feats if f["properties"]["kind"] == "municipality"]
    kept_munis, dropped = [], []
    for m in munis:
        (kept_munis if m["properties"].get("ine", "").startswith("48")
         else dropped).append(m)
    if dropped:
        print("  foráneos descartados:",
              [m["properties"]["name"]["es"] for m in dropped], file=sys.stderr)

    # parentesco: centroide del anillo mayor contra los municipios de Bizkaia;
    # distritos/barrios cuyo parent no es de Bizkaia se descartan también
    children = []
    for f in feats:
        if f["properties"]["kind"] == "municipality":
            continue
        ring = f["geometry"]["coordinates"][0][0]
        lat = sum(p[1] for p in ring) / len(ring)
        lon = sum(p[0] for p in ring) / len(ring)
        for m in kept_munis:
            poly = [(p[1], p[0]) for p in m["geometry"]["coordinates"][0][0]]
            if point_in_polygon(lat, lon, poly):
                f["properties"]["parent"] = m["properties"]["name"]["es"]
                children.append(f)
                break
        else:
            print(f"  descartado (sin municipio de Bizkaia): "
                  f"{f['properties']['name']['es']}", file=sys.stderr)
    feats = kept_munis + children

    counts = {}
    for f in feats:
        counts[f["properties"]["kind"]] = counts.get(f["properties"]["kind"], 0) + 1

    out = {
        "type": "FeatureCollection",
        "meta": {
            "source": "OpenStreetMap (Overpass)",
            "license": "ODbL 1.0 © OpenStreetMap contributors",
            "generated": date.today().isoformat(),
            "generator": "emap-labs/datasets/neighborhoods/build.py",
            "territory": "bizkaia",
            "counts": counts,
            "notes": "Barrios (admin_level 10) solo los mapeados en OSM; "
                     "municipios y distritos completos.",
        },
        "features": feats,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "neighborhoods.json"
    target.write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
    kb = target.stat().st_size // 1024
    orphans = [f["properties"]["name"]["es"] for f in feats
               if f["properties"]["kind"] != "municipality"
               and "parent" not in f["properties"]]
    print(f"OK → {target} ({kb} KB) · {counts}"
          + (f" · sin parent: {orphans}" if orphans else ""))


if __name__ == "__main__":
    main()
