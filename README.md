# emap/labs

`INFRAESTRUCTURA DE INTELIGENCIA GEOGRÁFICA · EUSKADI → EUROPA`

[![evals](https://github.com/r3tr0eth/emap-labs/actions/workflows/evals.yml/badge.svg)](https://github.com/r3tr0eth/emap-labs/actions/workflows/evals.yml)
[![Licencia](https://img.shields.io/badge/c%C3%B3digo-Apache--2.0-blue)](LICENSE)
[![Datos](https://img.shields.io/badge/datos-CC--BY--4.0%20%2F%20ODbL-green)](#licencias)
[![Release](https://img.shields.io/github/v/tag/r3tr0eth/emap-labs?label=datasets)](releases/RELEASE-NOTES.md)

Laboratorio de datos e IA detrás de [emap](https://emap-next.vercel.app):
datasets urbanos versionados, búsqueda semántica, RAG geoespacial y
benchmarks de retrieval en español y euskera. emap es el producto y el primer
consumidor de todo lo que sale de aquí.

*EN: Open geographic-retrieval benchmark (Spanish/Basque) and versioned urban
mobility datasets for the Basque Country. Reproducible in three commands.*

[Benchmark](#benchmark-de-retrieval-eseu) ·
[Reproducir](#reproducir-en-tres-comandos) ·
[Datasets](#datasets) ·
[Ética](#ética-y-limitaciones) ·
[Citar](#cómo-citar)

## Benchmark de retrieval ES/EU

Corpus dorado de **133 casos** de búsqueda geográfica hiperlocal sobre **21
categorías** (fuentes, aseos, parking, transporte, DEA, farmacias,
bibliotecas…) en español y euskera, con split **held-out estricto** (54
casos que jamás se usan para calibrar) y casos de abstención
(`answerable: false` — el retriever que inventa, falla). El euskera se
coteja con **Itzuli**, el traductor neuronal del Gobierno Vasco — no es
euskera artificial de traducción automática sin revisar.

Resultados (k=5, 2026-07-09):

| Retriever | dev ES | **held-out ES** | dev EU | **held-out EU** |
|---|---|---|---|---|
| baseline keywords+geo | 73% | **60%** | 69% | 62% |
| **híbrido keywords→semántico** (MiniLM-L12 mult.) | **81%** | 58% | 74% | **66%** |

Dos hallazgos centrales: **con euskera correcto, la etapa semántica apenas
aporta en EU** (los embeddings multilingües actuales flojean en euskera), y
**al pasar de 13 a 21 categorías el híbrido pierde el held-out ES contra el
baseline** — el modelo actual no escala con el espacio de categorías.
Cuantificar ambas brechas por modelo es el objetivo del benchmark.
Metodología, lecciones y resultados por modelo:
[`evals/README.md`](evals/README.md).

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
  url     = {https://github.com/r3tr0eth/emap-labs},
  version = {0.1}
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
