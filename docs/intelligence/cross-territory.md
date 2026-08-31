# Evaluación cross-territory

## Corte 2026-08-30

| Territorio / split | baseline ES | baseline EU | hybrid MiniLM ES |
|---|---:|---:|---:|
| Euskadi development | 58/82 (70%) | 58/82 (70%) |  — |
| Euskadi held-out | 16/29 (55%) | 15/29 (51%) |  — |
| Madrid development | 46/60 (76%) | no aplica | 53/60 (88%) |
| Madrid held-out | 13/19 (68%) | no aplica | 14/19 (74%) |

Semantic MiniLM Madrid obtuvo 46/60 (76%) en development y 11/19 (57%) en
held-out. Estos resultados no sustituyen las series Euskadi ni se usan para
recalibrar thresholds.

La tabla compara las ejecuciones disponibles del corte: no se ejecutó todavía
semantic/hybrid Euskadi en esta misma matriz porque el perfil semántico requiere
el entorno de modelos del servicio. Los resultados baseline son comparables solo
como referencia de escala; los corpus no son equivalentes.

## Métrica

Para dos splits comparables se usa la diferencia en puntos porcentuales:

```text
cross_territory_degradation = score(Madrid held-out)
                         - score(Euskadi held-out ES)
```

En el baseline disponible es `68% - 55% = +13 pp` (Madrid supera a Euskadi en
este corte), por lo que no debe llamarse “degradación” positiva ni interpretarse
como generalización europea. Los corpus tienen distinto tamaño, categorías,
idiomas y distribución de dificultad; se necesita un benchmark equilibrado
antes de extraer conclusiones causales.
