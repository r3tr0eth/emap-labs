# Packs territoriales de Intelligence

Un pack territorial de Labs declara cómo ejecutar el mismo pipeline sobre un
conjunto de datos. No contiene lógica `if territory == ...` ni redefine el
schema de POI.

## Contrato mínimo

`regions/<id>/region.yaml` contiene:

| Campo | Función |
|---|---|
| `version` | versión visible del snapshot territorial |
| `bbox` | `[min_lon, min_lat, max_lon, max_lat]` |
| `languages` | idiomas evaluables; debe incluir `es` |
| `layers` | `layer_id → ruta relativa` dentro del data root |
| `evaluation` | corpus y landmarks del territorio |
| `retrieval.production_profile` | perfil modelo/calibración desplegable |
| `freshness_sla_days` | overrides territoriales de SLA |
| `attribution` | atribución que acompaña la respuesta |

El adapter de cada fuente debe escribir el JSON normalizado y sus metadatos.
El registro solo lo localiza y valida; no transforma datos ni oculta ausencias.

## Estado

| Territorio | Estado Labs | Evidencia | Siguiente condición |
|---|---|---|---|
| Euskadi | **IMPLEMENTADO** | 22 capas, 27.515 POIs, corpus dev/held-out/challenge, perfil e5large | Formalizar confidence y response contract |
| Madrid | **PARCIAL / pack v0.1 ejecutable** | 1 capa oficial, 2.306 POIs, freshness y 18 casos dev; baseline 77%, semantic 83%, hybrid 88% | segunda capa P0 + 30–50 casos dev; held-out sigue cerrado |
| Tenerife | **PARCIAL / scaffold** | existe `region.yaml`, pero no pasa el contrato runtime por falta de capas y evaluación | decidir si se archiva o completa después de Madrid |

Madrid funciona en el mapa porque el basemap es global, el geocoder tiene un
pase nacional/Madrid y OTP contiene feeds de Madrid. Nada de eso creaba un
índice Labs. Desde Madrid v0.1, `service/app.py`, evals y freshness pueden
cargar el mismo pack territorial que Euskadi, hoy limitado a fuentes de beber.

La selección verificada de fuentes Madrid se mantiene en
[`madrid-sources.md`](madrid-sources.md). Una fuente pasa de candidata a
aceptada solo cuando tiene adapter reproducible, licencia/atribución, freshness
y casos development. Fuentes de beber ya cumple ese gate; held-out se creará y
sellará cuando el pack tenga varias capas y antes de calibrar con esos casos.

## Medición de reutilización Madrid

El sprint de ingesta debe reportar:

```text
reutilización = líneas no territoriales reutilizadas /
                líneas totales necesarias para activar Madrid
```

Se cuentan por separado adapter/configuración, normalización común, retrieval,
evidence y eval harness. El objetivo no es maximizar el porcentaje maquillando
adapters inevitables: cualquier transformación específica debe permanecer en
el borde Source → Adapter.
