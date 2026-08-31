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
| Madrid | **PARCIAL / pack v0.3 ejecutable** | 3 capas oficiales, 9.767 POIs aceptados, 60 dev + 19 held-out sellados; dev hybrid 53/60 (88%), held-out hybrid 14/19 (74%) | evaluar cross-territory y cerrar MCP |
| Tenerife | **PARCIAL / scaffold** | existe `region.yaml`, pero no pasa el contrato runtime por falta de capas y evaluación | decidir si se archiva o completa después de Madrid |

Madrid funciona en el mapa porque el basemap es global, el geocoder tiene un
pase nacional/Madrid y OTP contiene feeds de Madrid. Nada de eso creaba un
índice Labs. En el corte de código multi-territorio, `service/app.py` puede
servir el pack de Madrid y el de Euskadi simultáneamente mediante
`RuntimeRegistry`; el despliegue público sigue pendiente de promoción y el
pack Madrid v0.3 ya incluye fuentes, parking y aparcabicis.

La selección verificada de fuentes Madrid se mantiene en
[`madrid-sources.md`](madrid-sources.md). Una fuente pasa de candidata a
aceptada solo cuando tiene adapter reproducible, licencia/atribución, freshness
y casos development. El pack v0.3 cumple ese gate para sus tres capas; el
held-out está sellado y excluido de calibración.

## Medición de reutilización Madrid

Cada adapter Madrid reporta una métrica deliberadamente gruesa y auditable:

```text
territorial_reuse_ratio = etapas reutilizadas sin código territorial / 6
```

Las seis etapas son adquisición, adapter de formato, geo-normalización, schema
POI, pack territorial y Core/retrieval/evidence. La salida publica las etapas
reutilizadas y específicas; cualquier transformación específica permanece en
el borde Source → Adapter. Parking y aparcabicis registran 4/6 (0,667) con
esta definición conservadora.
