# emap/labs

`INFRAESTRUCTURA DE INTELIGENCIA GEOGRÁFICA · EUSKADI → EUROPA`

[![evals](https://github.com/r3tr0eth/emap-labs/actions/workflows/evals.yml/badge.svg)](https://github.com/r3tr0eth/emap-labs/actions/workflows/evals.yml)
[![Licencia](https://img.shields.io/badge/c%C3%B3digo-Apache--2.0-blue)](LICENSE)
[![Datos](https://img.shields.io/badge/datos-CC--BY--4.0%20%2F%20ODbL-green)](#licencias)
[![Release](https://img.shields.io/github/v/tag/r3tr0eth/emap-labs?label=datasets)](releases/RELEASE-NOTES.md)
[![DOI](https://zenodo.org/badge/1295202233.svg)](https://doi.org/10.5281/zenodo.21282784)

Laboratorio de datos e IA detrás de [emap](https://emap-next.vercel.app):
datasets urbanos versionados, búsqueda semántica, RAG geoespacial y
benchmarks de retrieval en español y euskera. emap es el producto y el primer
consumidor de todo lo que sale de aquí.

*EN: Open geographic-retrieval benchmark (Spanish/Basque) and versioned urban
mobility datasets for the Basque Country. Reproducible in three commands.*

[Benchmark](#benchmark-de-retrieval-eseu) ·
[MCP](#emap-desde-tu-agente-mcp) ·
[Reproducir](#reproducir-en-tres-comandos) ·
[Datasets](#datasets) ·
[Ética](#ética-y-limitaciones) ·
[Citar](#cómo-citar)

## Benchmark de retrieval ES/EU

Corpus dorado de **139 casos** de búsqueda geográfica hiperlocal sobre **22
capas** (fuentes, aseos, parking, transporte, DEA, farmacias, bibliotecas,
cimas…) en español y euskera, con split **held-out estricto** (54
casos que jamás se usan para calibrar) y casos de abstención
(`answerable: false` — el retriever que inventa, falla). El euskera se
coteja con **Itzuli**, el traductor neuronal del Gobierno Vasco — no es
euskera artificial de traducción automática sin revisar.

Resultados held-out (k=5, cada modelo en su config dev-óptima, 2026-07-24):

| Retriever | dev ES | **held-out ES** | dev EU | **held-out EU** |
|---|---|---|---|---|
| baseline keywords+geo | 74% | 60% | 71% | 62% |
| híbrido · MiniLM-L12 mult. | 80% | 60% | 76% | 66% |
| híbrido · mpnet-base mult. | 79% | 64% | 73% | 66% |
| **híbrido · multilingual-e5-large** | **88%** | **75%** | **84%** | **81%** |

Hallazgo central: **la brecha del euskera no era del idioma, era del modelo**.
Con MiniLM la etapa semántica apenas aportaba en EU; con **e5-large** el
held-out EU llega al 81% y supera al ES. Además el umbral de abstención
**no transfiere entre modelos** (τ=0.50 dejaba muerta la abstención de e5;
recalibrado a 0.80 pasa a mejor de todos). Informe completo —metodología,
coste/latencia, limitaciones—: **[`BENCHMARK.md`](BENCHMARK.md)**;
lecciones del harness: [`evals/README.md`](evals/README.md).

## emap desde tu agente (MCP)

**El primer servidor MCP de movilidad hiperlocal**: existen MCPs genéricos
de GTFS y de OSM, pero ninguno expone inteligencia de movilidad local a
agentes — búsqueda semántica bilingüe ES/EU, contexto de lugar, rutas
multimodales con infraestructura propia y *el monte en transporte público*.
Cinco herramientas ([`mcp/`](mcp/README.md)):

| Tool | Pregunta que responde |
|---|---|
| `search_places` | "dónde beber agua" · "haurra aldatzeko lekua" (con abstención honesta) |
| `nearby_pois` | el DEA / aseo / aparcabici / cima más cercana |
| `explain_place` | qué barrio es esto y qué servicios tiene alrededor |
| `plan_route` | ruta real transit/walk/bike/car (OSRM/OTP propios) |
| `plan_hike` | qué cima hago hoy en transporte público (2.825 cimas × 9 redes) |

```json
{ "mcpServers": { "emap": {
    "command": "/ruta/a/emap-labs/.venv/bin/python",
    "args": ["/ruta/a/emap-labs/mcp/server.py"] } } }
```

Toda respuesta lleva `attribution` (ODbL + GTFS + CC-BY-4.0). Criterio de
aceptación cumplido y verificado por protocolo: *"¿dónde dejo la bici cerca
de San Mamés?"* → aparcabicis a 47 m, con atribución.

## Reproducir en tres comandos

```bash
git clone https://github.com/r3tr0eth/emap-labs && cd emap-labs
pip install -r evals/requirements.txt
python evals/run.py --retriever hybrid --lang eu --split heldout
```

Autocontenido: el snapshot de datos vive en `evals/data/` (el mismo que usa
el [CI](https://github.com/r3tr0eth/emap-labs/actions/workflows/evals.yml),
con gates de regresión en cada push). Cada JSON de `evals/results/` versiona
la configuración exacta (modelo, τ, tie-window) con la que se obtuvo.

## Datasets

Release **v0.1** (2026-07): 7 datasets / 12.732 registros de movilidad e
infraestructura urbana de Euskadi (foco Bizkaia) — fuentes, aseos, parking,
DEA, EV, cámaras y paradas multi-red (metro, Euskotren, Cercanías, Bilbobus,
Bizkaibus). Detalle y metadatos: [`releases/RELEASE-NOTES.md`](releases/RELEASE-NOTES.md).
Cada dataset declara fuente, licencia, fecha y cobertura estimada solo cuando
es honestamente estimable. Pipelines reproducibles en [`datasets/`](datasets/README.md).

## Estructura

```
evals/      corpus dorado ES/EU, harness, resultados versionados
datasets/   pipelines de datasets propios (places, barrios, scores)
service/    servicio semántico (FastAPI + fastembed, corre en VPS propio)
releases/   releases versionadas de datasets
docs/       roadmap, ética de datos, informes de cobertura
```

## Principios

- `DATOS ANTES QUE MODELOS` — no se entrena ni fine-tunea nada en este horizonte.
- `NO SE FINGE` — lo que no se puede medir se omite; los evals premian decir "no lo sé".
- `DOGFOODING` — nada cuenta como hecho hasta que emap lo usa en producción.
- `ES/EU EN PARIDAD` — el euskera se escribe, no se traduce.

Regla de decisión: cada desarrollo debe mejorar emap, ser reutilizable,
publicable como open source o vendible. Si no cumple ninguna, no se hace.

## Ética y limitaciones

[`docs/ETICA-DATOS.md`](docs/ETICA-DATOS.md) es regla dura, no aspiración:
**se describe la infraestructura, jamás a las personas**. Limitaciones
declaradas: sesgo de mapeo OSM (Bilbao mejor cubierto que la periferia — se
declara en `coverage.notes` de cada dataset), corpus sintético escrito por
una persona (las consultas reales anonimizadas lo sustituirán), y umbrales
calibrados solo sobre dev — por eso el held-out manda.

## Cómo citar

Si usas el benchmark, el corpus o los datasets, cita el repositorio
(GitHub: *Cite this repository*, desde [`CITATION.cff`](CITATION.cff)):

```bibtex
@software{emaplabs2026,
  author  = {Jiménez, Gaizka},
  title   = {EMAP Labs: geographic retrieval benchmark and mobility
             datasets for the Basque Country (Spanish/Basque)},
  year    = {2026},
  doi     = {10.5281/zenodo.21282784},
  url     = {https://github.com/r3tr0eth/emap-labs},
  version = {0.1.1}
}
```

## Agradecimientos

Datos de [OpenStreetMap](https://www.openstreetmap.org/copyright) y
[Open Data Euskadi](https://opendata.euskadi.eus). Euskera del corpus
cotejado con [Itzuli](https://www.euskadi.eus/itzuli/) (Gobierno Vasco).
Embeddings servidos con [fastembed](https://github.com/qdrant/fastembed).

## Licencias

- **Código**: [Apache-2.0](LICENSE).
- **Corpus de evaluación propio** (`evals/*.yaml`, docs): [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/deed.es) — atribución "EMAP Labs".
- **Datos derivados**: lo derivado de [OpenStreetMap](https://www.openstreetmap.org/copyright) mantiene **ODbL**; lo derivado de [Open Data Euskadi](https://opendata.euskadi.eus) mantiene **CC-BY-4.0** con atribución al portal. Cada dataset declara su fuente y licencia en sus metadatos.
