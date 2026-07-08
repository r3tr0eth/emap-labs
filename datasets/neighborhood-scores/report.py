#!/usr/bin/env python3
"""Informe institucional de cobertura de infraestructura → docs/informes/.

Uso analítico del coverage_index conforme a ETICA-DATOS.md: señala DÉFICITS
de servicio público (dónde falta inversión), nunca "barrios malos". HTML
autocontenido (tokens de marca inline) para compartir con instituciones.

    ../emap-next/.venv/bin/python datasets/neighborhood-scores/report.py
"""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

LABS = Path(__file__).resolve().parents[2]
SCORES = LABS / ".." / "emap-next" / "data/processed/neighborhoods/scores.json"
OUT = LABS / "docs" / "informes"

COMPONENT_LABEL = {
    "services": "Servicios básicos (fuentes, aseos, DEA)",
    "mobility": "Transporte público (paradas, ferroviario ×3)",
    "cycling": "Ciclabilidad (bidegorris, aparcabicis)",
    "traffic": "Presión de tráfico (inversa de incidencias)",
}


def esc(x) -> str:
    return html.escape(str(x))


def row(u: dict) -> str:
    c = u["counts"]
    return (f"<tr><td>{esc(u['name']['es'])}"
            f"{' <span class=parent>(' + esc(u['parent']) + ')</span>' if u.get('parent') else ''}</td>"
            f"<td class=n>{u['coverage_index']}</td>"
            f"<td class=n>{c['fountains']}</td><td class=n>{c['toilets']}</td>"
            f"<td class=n>{c['defib']}</td>"
            f"<td class=n>{sum(c[k] for k in ('metro', 'euskotren', 'cercanias', 'bilbobus', 'bizkaibus'))}</td>"
            f"<td class=n>{u['bike_km']:.1f}</td>"
            f"<td class=n>{u['area_km2']:.1f}</td></tr>")


def table(units: list[dict], caption: str) -> str:
    head = ("<tr><th>Unidad</th><th>Índice</th><th>Fuentes</th><th>Aseos</th>"
            "<th>DEA</th><th>Paradas</th><th>Bidegorri km</th><th>km²</th></tr>")
    return (f"<h3>{esc(caption)}</h3><div class=tw><table>{head}"
            + "".join(row(u) for u in units) + "</table></div>")


def main() -> None:
    doc = json.loads(SCORES.read_text())
    scores = doc["scores"]
    barrios = sorted((u for u in scores if u["kind"] == "neighborhood"),
                     key=lambda u: u["coverage_index"])
    munis = sorted((u for u in scores if u["kind"] == "municipality"),
                   key=lambda u: u["coverage_index"])

    body = f"""
<h1>Cobertura de infraestructura urbana — Bizkaia</h1>
<p class=meta>emap/labs · {date.today().isoformat()} · datos: OpenStreetMap (ODbL),
GTFS oficiales, incidencias de tráfico de Euskadi · método: percentil de densidad
por km² dentro de cada grupo (barrios con barrios, municipios con municipios)</p>

<div class=ethics>
<strong>Lectura correcta de este informe.</strong> El índice mide la
<em>provisión de infraestructura pública</em> de cada zona, no su calidad de
vida ni a sus habitantes. Un índice bajo señala una <strong>deuda de
inversión de la administración con esa zona</strong> — es un argumento para
priorizarla, nunca para evitarla. Este informe no usa ni usará datos de
criminalidad, renta o demografía (regla dura del proyecto:
<code>ETICA-DATOS.md</code>). Advertencia de sesgo: los conteos derivados de
OpenStreetMap reflejan también la intensidad de mapeo de cada zona.
</div>

<h2>Dónde falta inversión primero</h2>
{table(barrios[:10], 'Barrios de Bilbao con menor cobertura (de 26 mapeados en OSM)')}
{table(munis[:15], 'Municipios de Bizkaia con menor cobertura (de 113)')}

<h2>Referencia: mayor cobertura</h2>
{table(list(reversed(barrios[-5:])), 'Barrios de Bilbao con mayor cobertura')}
{table(list(reversed(munis[-5:])), 'Municipios con mayor cobertura')}

<h2>Componentes del índice</h2>
<ul>{''.join(f'<li><strong>{k}</strong> — {esc(v)}</li>' for k, v in COMPONENT_LABEL.items())}</ul>
<p>El índice es la media de los cuatro componentes (percentiles 0–100).
Los conteos crudos acompañan siempre a cada fila: <em>el índice ordena,
el número manda</em>. Datos y metodología reproducibles:
<code>github.com/r3tr0eth/emap-labs</code> (datasets/neighborhood-scores).</p>
"""

    page = f"""<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Cobertura de infraestructura — Bizkaia · emap/labs</title>
<style>
:root {{ --ink:#16181D; --paper:#E9EBE4; --surface:#FFF; --border:#D8DBD1;
  --t2:#5A5F58; --t3:#6B7066; --accent-text:#486312; }}
* {{ box-sizing:border-box }}
body {{ margin:0; padding:32px 20px; background:var(--paper); color:var(--ink);
  font:15px/1.55 -apple-system, 'Segoe UI', sans-serif; }}
main {{ max-width:860px; margin:0 auto }}
h1 {{ font-size:26px; letter-spacing:-.01em; margin:0 0 4px }}
h2 {{ font-size:18px; margin:36px 0 4px }}
h3 {{ font-size:13px; margin:20px 0 8px; color:var(--t2);
  text-transform:uppercase; letter-spacing:.12em;
  font-family:ui-monospace,monospace; font-weight:500 }}
.meta {{ color:var(--t3); font-size:13px; margin:0 0 20px }}
.ethics {{ background:var(--surface); border:1px solid var(--border);
  border-left:3px solid var(--accent-text); border-radius:8px;
  padding:14px 16px; font-size:14px }}
.tw {{ overflow-x:auto }}
table {{ border-collapse:collapse; width:100%; background:var(--surface);
  border:1px solid var(--border); border-radius:8px; font-size:13.5px }}
th,td {{ padding:7px 10px; text-align:left; border-top:1px solid #EEF0E9 }}
th {{ font-family:ui-monospace,monospace; font-size:10px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--t3); border-top:none }}
td.n {{ text-align:right; font-family:ui-monospace,monospace }}
.parent {{ color:var(--t3); font-size:12px }}
code {{ font-family:ui-monospace,monospace; font-size:.92em }}
li {{ margin:3px 0 }}
</style></head><body><main>{body}</main></body></html>"""

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"cobertura-bizkaia-{date.today().strftime('%Y-%m')}.html"
    target.write_text(page)
    print(f"OK → {target} ({target.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
