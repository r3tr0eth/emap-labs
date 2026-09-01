# Evaluación cross-territory

## Corte 2026-08-31 (development)

Ejecutado con `evals/run.py`; resultados en `evals/results/*-2026-08-31.json`,
que ya registran `corpus_sha256` y latencia agregada del run (avg/max/total,
medida consulta a consulta pero persistida como agregado). Corpus: Euskadi v1
(`d48dc464…`, 82 casos dev puntuables tras excluir 3 huecos de datos
conocidos), Madrid v0.2.0 (`191c2749…`, 60 casos dev; el corpus es solo ES,
declarado en `regions/madrid/region.yaml`).

| Territorio (dev) | baseline ES | baseline EU | hybrid MiniLM ES | hybrid MiniLM EU | hybrid E5 Large ES | hybrid E5 Large EU |
|---|---:|---:|---:|---:|---:|---:|
| Euskadi | 58/82 (70%) | 58/82 (70%) | 64/82 (78%) | 60/82 (73%) | 70/82 (85%) | 68/82 (82%) |
| Madrid | 46/60 (76%) | no aplica | 53/60 (88%) | no aplica | 53/60 (88%) | no aplica |

**E5 Large medido por primera vez de verdad el 2026-09-01** (VPS,
`hybrid-e5large-*-2026-09-01.json`), tras arreglar un bug del harness:
`SemanticEncoder` ignoraba `EMAP_RETRIEVER_PROFILE`, así que **todos los
resultados "e5large" anteriores (incluidos los del 2026-08-05) habían
ejecutado MiniLM con etiqueta falsa** (producción no se vio afectada: el
factory del servicio pasa el perfil explícito). Desde este fix la `config`
del artefacto sale del encoder que ejecutó, no de metadata.

Con el modelo real: **+7 pp ES y +9 pp EU sobre MiniLM en Euskadi dev**
(70/82 y 68/82; por caso: e5 gana 9 y pierde 3 en ES, gana 11 y pierde 3 en
EU) y también gana en challenge (30/47=63% ES y 31/47=65% EU vs 26/47=55% y
28/47=59% de MiniLM). En Madrid dev empata en total (53/60) con un matiz:
e5 resuelve un caso de parking más pero responde un caso `unsupported` donde
MiniLM se abstenía. Latencia media por consulta: 22–37 ms (vs ~8 ms MiniLM).

Gates de CI fijados con esta evidencia: Madrid e5large dev min-pass 85
(medido 88, mismo margen que MiniLM); Euskadi e5large dev 80 ES / 78 EU —
deliberadamente **por encima del rendimiento de MiniLM** (78/73), de modo que
una regresión al modelo pequeño (la clase de bug que se acaba de arreglar)
pondría el gate en rojo por sí sola.

## Held-out — última ejecución registrada por fichero

| Territorio / split | baseline ES | baseline EU | hybrid MiniLM ES | hybrid MiniLM EU |
|---|---:|---:|---:|---:|
| Euskadi held-out (29 casos, corpus v1) | 17/29 (58%) | sin ejecución registrada | 18/29 (62%) | 18/29 (62%) |
| Madrid held-out (19 casos, corpus 0.2.0, sellado) | 13/19 (68%) | no aplica | 14/19 (73%) | no aplica |

Todos los porcentajes de esta página usan la convención de `run.py` (redondeo
hacia abajo).

Semantic MiniLM Madrid: 46/60 (76%) dev y 11/19 (57%) held-out.

Nota de trazabilidad: el corte 2026-08-30 de este documento citaba 16/29 (55%)
y 15/29 (51%) para el held-out de Euskadi; ningún fichero de `evals/results/`
respalda esas cifras. Las de la tabla salen de los JSON del 2026-08-05
recortados al split vigente tras el re-split del corpus (held-out 53→29
casos; los `ho2-*` pasaron a `challenge`): mismo run original, mismos
resultados por caso, filtrados a los 29 casos que siguen siendo held-out. Baseline EU no tiene ejecución held-out registrada
sobre el corpus actual: se medirá en el job manual de CI, nunca para calibrar.

## Métrica

Para dos splits comparables se usa la diferencia en puntos porcentuales:

```text
cross_territory_degradation = score(Madrid held-out)
                         - score(Euskadi held-out ES)
```

Con los ficheros actuales, baseline ES: `68% − 58% = +10 pp` (Madrid supera a
Euskadi en este corte; exacto: +9,8 pp); hybrid MiniLM ES: `73% − 62% =
+11 pp` (exacto: +11,6 pp). No debe
llamarse "degradación" positiva ni interpretarse como generalización europea.

## Limitaciones estadísticas

- Madrid held-out tiene n=19: **un solo caso mueve el resultado 5,3 pp**.
- Euskadi held-out tiene n=29: un caso son 3,4 pp.
- Los corpus difieren en tamaño, categorías, idiomas y distribución de
  dificultad; los números son comparables solo como referencia de escala.
- Ninguna cifra de esta página se usa para recalibrar thresholds; el held-out
  se ejecuta solo como decisión final (regla en `evals.yml` y en el seal).
