# EMAP Labs v0.3.0-rc.1 — Intelligence/Core multi-territorio

Prerelease técnica para validar que un mismo seam territorial, pipeline de
retrieval y contrato de evidencia funcionan sobre Euskadi y Madrid. No es la
integración completa de Madrid ni implica un deploy de producción.

Revisión 2026-08-31: estas notas se actualizan al corte multi-territorio real
(la versión del 2026-08-29 describía 1 adapter Madrid, 18 casos dev y un
territorio por proceso). La RC no está tagueada; el tarball de datasets sigue
siendo el del 29-ago y debe regenerarse antes del tag.

## Qué incorpora

- registro territorial versionado (`RuntimeRegistry` inmutable) sirviendo
  Euskadi y Madrid simultáneamente en una instancia, con resolución por
  request y errores explícitos sin fallback;
- 3 adapters oficiales de Madrid (`fountains`, `parking`, `bikepark`):
  9.767 POIs con estado, procedencia de coordenadas, freshness, checksum,
  cobertura y calidad;
- EMAPBench Madrid v0.2.0: 60 casos dev + 19 held-out sellados
  (`evals/madrid-heldout-seal.json`, calibración excluida);
- perfiles versionados MiniLM/MPNet/e5-large y separación estricta
  dev/held-out (held-out solo por workflow manual; Madrid como medición única);
- Response Contract v1 (`intelligence.response.v1`) con validación automática,
  estados explícitos, evidencia, freshness por SLA territorial, confidence
  explicable y limitación `STALE_EVIDENCE`;
- telemetría mínima privacy-first en `GET /metrics` con contadores separados
  por `answer_status`;
- MCP 0.1.2 desplegado en `vps.emapapp.com/mcp` (5 tools, smoke público OK).
  Las mejoras de contrato de esta revisión (`took_ms` en `search_places`,
  `STALE_EVIDENCE`, `schema_version` en errores) están en el repo y requieren
  redeploy: el build desplegado hoy aún no las sirve.

## Resultados de release (corte dev 2026-08-31)

| Territorio / split | Baseline | Semantic | Hybrid MiniLM | Hybrid E5 Large |
|---|---:|---:|---:|---:|
| Madrid dev ES (60) | 76% | 76% MiniLM | 88% | 88% |
| Euskadi dev ES (82) | 70% | — | 78% | **85%** |
| Euskadi dev EU (82) | 70% | — | 73% | **82%** |
| Madrid held-out ES (19, sellado) | 68% | 57% MiniLM | 73% | pendiente (medición única) |
| Euskadi held-out ES (29) | 58% | — | 62% | pendiente |
| Euskadi held-out EU (29) | sin ejecución | — | 62% | pendiente |

Fechas por fila: dev MiniLM/baseline del 2026-08-31 (semantic Madrid:
2026-08-30); dev E5 Large del 2026-09-01 (VPS); held-out Madrid del
2026-08-30; held-out Euskadi del 2026-08-05, recortado al split vigente
(mismo run, mismos resultados por caso). Porcentajes con la convención de
`run.py` (redondeo hacia abajo).

Los held-out se ejecutaron una sola vez por corte y no se usaron para ajustar
thresholds ni casos. Los números "e5-large" publicados el 29-ago quedan
retirados: un bug del harness (arreglado el 2026-09-01, con test de
regresión) hacía que toda ejecución "e5large" cargara en realidad MiniLM. La
primera medición real del perfil (arriba) da +7/+9 pp sobre MiniLM en Euskadi
dev y también gana en challenge (63%/65% vs 55%/59%).

## Asset de datasets

`emap-labs-datasets-v0.3.0-rc.1.tar.gz` (corte 2026-08-29) contiene 8 datasets
y 17.241 registros:

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

Pendiente de regenerar con parking y bikepark de Madrid antes de taguear la
RC. Cada entrada incluye fuente, licencia, fecha, SHA-256, cobertura y
métricas de calidad. No se publica `coverage.completeness` cuando no puede
estimarse con honestidad.

## Límites explícitos de esta RC

- Madrid tiene 3 de las 5–8 fuentes objetivo, solo ES, y sus datos en prod
  dependen de re-ingesta (SLA 2 días; estaban stale el 2026-08-31).
- El held-out de E5 Large (Euskadi y Madrid) sigue pendiente del job manual;
  los umbrales held-out 70/68 de evals.yml proceden de la era del bug y deben
  revisarse conscientemente antes de la ejecución única.
- Confidence no agrega los factores al score; sin factor geográfico ni
  detección de conflicto de evidencia.
- Telemetría sin dimensión endpoint/tool ni persistencia; MCP sin telemetría.
- La suite completa de Labs (45 tests) está verde en local; su primera
  ejecución en GitHub Actions está pendiente de push.

## Reproducibilidad

```bash
python releases/build_release.py --version 0.3.0-rc.1 --date 2026-08-29
python evals/run.py --retriever baseline --territory madrid --lang es --split dev
python evals/run.py --retriever hybrid --profile minilm --territory madrid --lang es --split dev
python evals/run.py --retriever hybrid --profile minilm --lang es --split dev
```

Código Apache-2.0; corpus EMAP CC-BY-4.0; datos derivados conservan las
licencias y atribuciones indicadas en `manifest.json`.
