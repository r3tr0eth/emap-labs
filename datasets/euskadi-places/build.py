#!/usr/bin/env python3
"""Places de Open Data Euskadi → POIs normalizados (CANDIDATOS-OPENDATA P1/P2).

Patrón r01: la URL /data/ del catálogo devuelve un XML de metadatos con
pares formato→enlace; de ahí se toma el GeoJSON (ds_localizaciones) o el
JSON (serie ds_recursos_turisticos, que trae lat/lon por registro).

Ética (ETICA-DATOS.md): se descartan campos con nombres de personas
(titular de farmacia, etc.) — solo infraestructura y equipamiento.

Uso: python datasets/euskadi-places/build.py
Salida: ../emap-next/data/pois-euskadi/{pharmacy,sports,food,lodging,...}.json
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / ".." / "emap-next" / "data" / "pois-euskadi"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE  # la cadena TLS de euskadi.eus falla en macOS

# capa → (URL /data/ del catálogo r01, ficheros deseados dentro del XML)
R01 = "https://opendata.euskadi.eus"
SOURCES = {
    "pharmacy": (f"{R01}/contenidos/ds_localizaciones/farmacias_y_botiquines_euskadi/es_vpo/data/es_r01dtpd169816147a218fe87fe4e991bb14a74d2ee", ["farmacias.geojson"]),
    "library": (f"{R01}/contenidos/ds_localizaciones/bibliotecas_publicas_euskadi/es_centros/data/es_r01dpd014183085f46147e092b02d99f802c74141", ["geojson"]),
    "sports": (f"{R01}/contenidos/ds_localizaciones/censo_instalaciones_deportivas/es_vpo/data/es_r01dtpd016faed13ec2c9aadacab967322d5a92e49", ["geojson", "json"]),
    "food": (f"{R01}/contenidos/ds_recursos_turisticos/restaurantes_sidrerias_bodegas/es_res/data/es_r01dpd012794f7efc71d7cc67944adcc670301f3b", ["json"]),
    "lodging": (f"{R01}/contenidos/ds_recursos_turisticos/hoteles_de_euskadi/es_aloja/data/es_r01dtpd15356997c73183cf7324545f576a0bf3eff", ["json"]),
    "hostel": (f"{R01}/contenidos/ds_recursos_turisticos/albergues_de_euskadi/es_aloja/data/es_r01dtpd15384536f6a18a7c6d6b6024c4995e92213", ["json"]),
    "camping": (f"{R01}/contenidos/ds_recursos_turisticos/campings_de_euskadi/es_aloja/data/es_r01dtpd015356c3991218c8760dcbf948af295e79b", ["json"]),
    "nature": (f"{R01}/contenidos/ds_recursos_turisticos/espacios_naturales_euskadi/es_natura/data/es_r01dpd0127952729dc16d650f9d7ed89eef42de13", ["json"]),
}

# campos que JAMÁS se copian (personas, no infraestructura)
PERSON_FIELDS = {"titular", "titular1", "titular2", "responsable", "contacto"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "emap-labs/0.1 (+github.com/r3tr0eth/emap-labs)"})
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        return r.read()


def r01_links(meta_url: str) -> dict[str, str]:
    """XML r01 → {nombre_fichero: url_absoluta} de los enlaces de descarga."""
    try:
        xml = fetch(meta_url).decode("iso-8859-1", errors="replace")
    except Exception as e:
        print(f"  meta KO ({e})")
        return {}
    out = {}
    for enlace in re.findall(r"enlace_descarga><!\[CDATA\[([^\]]+)\]\]", xml):
        url = enlace if enlace.startswith("http") else R01 + enlace
        out[url.rsplit("/", 1)[-1].lower()] = url
    return out


def norm_geojson(raw: bytes, layer: str) -> list[dict]:
    d = json.loads(raw)
    pois = []
    for f in d.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        p = {k.lower(): v for k, v in (f.get("properties") or {}).items()}
        name = p.get("nombre") or p.get("name") or p.get("documentname")
        if not name:  # farmacias no traen nombre → construir sin persona
            name = f"Farmacia ({p.get('direccion', '?')})" if layer == "pharmacy" else None
        if not name:
            continue
        tags = {k: str(v)[:120] for k, v in p.items()
                if k not in PERSON_FIELDS and v not in (None, "") and k not in ("nombre", "name")}
        pois.append({"name": {"es": str(name).strip(), "eu": str(name).strip()},
                     "lat": round(float(lat), 6), "lon": round(float(lon), 6), "tags": tags})
    return pois


def norm_turismo(raw: bytes) -> list[dict]:
    """Serie ds_recursos_turisticos: lista JSON con documentName + latwgs84."""
    try:
        d = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        d = json.loads(raw.decode("iso-8859-1", errors="replace"))
    recs = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
    pois = []
    for r in recs:
        p = {k.lower(): v for k, v in r.items()}
        lat, lon = p.get("latwgs84") or p.get("latitude"), p.get("lonwgs84") or p.get("longitude")
        name = p.get("documentname") or p.get("nombre")
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if not name or not (42.4 < lat < 43.6 and -3.6 < lon < -1.6):
            continue
        keep = ("municipality", "municipio", "territory", "address", "direccion",
                "phone", "telefono", "capacity", "categoria", "documentdescription")
        tags = {k: str(p[k])[:120] for k in keep if p.get(k)}
        pois.append({"name": {"es": str(name).strip(), "eu": str(name).strip()},
                     "lat": round(lat, 6), "lon": round(lon, 6), "tags": tags})
    return pois


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for layer, (meta, wanted) in SOURCES.items():
        print(f"■ {layer}")
        links = r01_links(meta)
        if not links:
            print("  sin enlaces — revisar URL del catálogo")
            continue
        pois: list[dict] = []
        for fname, url in links.items():
            if not any(w in fname for w in wanted):
                continue
            if fname.endswith("-padding.geojson") or "jsonp" in fname:
                continue
            try:
                raw = fetch(url)
            except Exception as e:
                print(f"  {fname}: KO ({e})")
                continue
            batch = (norm_geojson(raw, layer) if fname.endswith(".geojson")
                     else norm_turismo(raw))
            print(f"  {fname}: {len(batch)} POIs")
            pois.extend(batch)
        if not pois:
            print("  0 POIs — no se escribe")
            continue
        # dedupe por (nombre, celda ~50m)
        seen, clean = set(), []
        for p in pois:
            key = (p["name"]["es"], round(p["lat"], 3), round(p["lon"], 3))
            if key not in seen:
                seen.add(key)
                clean.append(p)
        path = OUT / f"{layer}.json"
        path.write_text(json.dumps({
            "generated": date.today().isoformat(),
            "source": "Open Data Euskadi (CC-BY 4.0)",
            "license": "CC-BY-4.0",
            "count": len(clean),
            "pois": clean,
        }, ensure_ascii=False))
        print(f"  → {path.name}: {len(clean)} POIs")
        total += len(clean)
    print(f"\nTOTAL: {total} POIs nuevos")


if __name__ == "__main__":
    main()
