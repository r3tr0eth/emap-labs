# EMAP Labs v0.3.0-rc.1 — Intelligence/Core multi-territorio

Prerelease técnica para validar que un mismo seam territorial, pipeline de
retrieval y contrato de evidencia funcionan sobre Euskadi y Madrid. No es la
integración completa de Madrid ni implica un deploy de producción.

## Qué incorpora

- registro territorial versionado para Euskadi y Madrid;
- adapter oficial de fuentes de agua del Ayuntamiento de Madrid;
- 2.306 POIs Madrid con estado, procedencia de coordenadas, freshness,
  checksum, cobertura y calidad;
- EMAPBench Madrid dev con 18 consultas geográficas, semánticas, ambiguas,
  imposibles y adversariales;
- perfiles versionados MiniLM/MPNet/e5-large y separación estricta dev/held-out;
- respuesta Labs con territorio, versión, retriever, evidencia, freshness,
  limitaciones y atribución;
- MCP 0.1.2 preparado para conservar la atribución territorial de Core.

## Resultados de release

| Territorio / split | Baseline | Semantic | Hybrid |
|---|---:|---:|---:|
| Madrid dev ES (18) | 77% | 83% MiniLM | 88% MiniLM |
| Euskadi dev ES (82) | 74% | — | 89% e5-large |
| Euskadi dev EU (82) | 71% | — | 84% e5-large |
| Euskadi held-out ES (29) | 58% | — | 79% e5-large |
| Euskadi held-out EU (29) | 51% | — | 82% e5-large |

El held-out se ejecutó una sola vez como gate final. No se utilizó para ajustar
thresholds ni casos.

## Asset de datasets

`emap-labs-datasets-v0.3.0-rc.1.tar.gz` contiene 8 datasets y 17.241 registros:

| Dataset | Registros | Fuente / licencia |
|---|---:|---|
| DEA Euskadi | 2.731 | Open Data Euskadi · CC BY 4.0 |
| Fuentes Euskadi | 8.968 | OpenStreetMap · ODbL |
| Aseos Euskadi | 967 | OpenStreetMap · ODbL |
| Aparcamientos Euskadi | 827 | OpenStreetMap · ODbL |
| Aparcabicis Euskadi | 1.077 | OpenStreetMap · ODbL |
| Playas Euskadi | 218 | OSM + Open Data Bizkaia · ODbL / CC BY 4.0 |
| Límites administrativos Bizkaia | 147 | OpenStreetMap · ODbL |
| Fuentes Madrid | 2.306 | Ayuntamiento de Madrid · CC BY 4.0 |

Cada entrada incluye fuente, licencia, fecha, SHA-256, cobertura y métricas de
calidad. No se publica `coverage.completeness` cuando no puede estimarse con
honestidad.

## Límites explícitos de esta RC

- Madrid solo tiene una de las 5–8 fuentes objetivo y 18 casos dev; no tiene
  held-out.
- El servicio carga un territorio por proceso; aún no atiende Euskadi y Madrid
  simultáneamente desde la misma instancia.
- El response contract y la calibración formal de confidence están parciales.
- La telemetría Intelligence todavía no está implementada.
- `https://vps.emapapp.com/mcp` devolvía 421 el 2026-08-28: el código 0.1.2
  está preparado, pero el redeploy y el smoke verde son una operación separada.

## Reproducibilidad

```bash
python releases/build_release.py --version 0.3.0-rc.1 --date 2026-08-29
python evals/run.py --retriever hybrid --profile e5large --lang es --split dev
python evals/run.py --retriever hybrid --profile minilm --territory madrid --lang es --split dev
```

Código Apache-2.0; corpus EMAP CC-BY-4.0; datos derivados conservan las
licencias y atribuciones indicadas en `manifest.json`.
