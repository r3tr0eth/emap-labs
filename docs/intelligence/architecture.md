# EMAP Core v0.1 — arquitectura efectiva

**Estado:** 2026-08-27. Este documento describe código existente y el seam
territorial mínimo introducido en el primer sprint Intelligence/Core.

EMAP Core v0.1 no es un microservicio nuevo. Es la composición de módulos ya
existentes detrás de interfaces comprobables:

```text
adapter de fuente
  → JSON normalizado por capa
  → regions/<id>/region.yaml
  → regions.registry.Territory
  → baseline / HybridRetriever
  → evidence + freshness + abstention
  → service /search
  → proxy emap-next /api/semantic-search
  → web o MCP

routing / temporal / realtime
  → emap-next/packages/*
  → /api/route y endpoints deterministas
  → web, móvil o MCP
```

No se ha unido artificialmente ambos caminos: el retrieval territorial vive
en Labs y routing sigue siendo autoridad de `emap-next/packages/routing`.
La integración se hará en contratos, no copiando lógica.

## Mapa de componentes

| Componente | Ubicación | Responsabilidad | Dependencias | Consumidores |
|---|---|---|---|---|
| Registro territorial | `regions/registry.py` + `regions/*/region.yaml` | Validar bbox, capas, evaluación, perfil y versión; resolver rutas | PyYAML, manifiesto | servicio, evals, evidence/freshness |
| Esquemas de dominio | `../emap-next/packages/schemas` | Contratos de POI, fuente, manifest y ruta | JSON Schema | API, catálogo, layers |
| Normalización de POI | `../emap-next/packages/layers` + pipelines `datasets/` | Convertir fuentes heterogéneas a entidades consumibles | schemas, adapters | datos de Labs y mapa |
| Retrieval baseline | `evals/baseline.py` | Keywords, atributos, nombre y orden geográfico | JSON por capa, `emap_geo` | evals, híbrido |
| Retrieval semántico | `evals/semantic_local.py` | Clasificar categoría; delegar filtros/geo al baseline | FastEmbed, perfil calibrado | servicio, evals |
| Perfiles reproducibles | `evals/retriever-config.json` + `retriever_config.py` | Unir modelo, threshold y tie-window | stdlib | CI, evals, producción |
| Evidence | `service/explain.py` | Fuente, licencia, actualización y explicación de categoría | registro + JSON de capa | `/search` |
| Freshness | `service/data_freshness.py` | Edad, SLA, estado y confidence cualitativa | registro + metadatos | `/search`, `/quality` |
| Servicio Intelligence | `service/app.py` | Cargar un territorio, buscar, abstenerse y exponer HTTP | módulos anteriores | proxy API |
| API compartida | `../emap-next/apps/api` | Proxy semántico y autoridad de rutas/datos | Labs + packages | web, móvil, MCP |
| MCP | `mcp/server.py` | Adapter estrecho para agentes, sin lógica territorial propia | API + servicio Labs | clientes MCP |

## Interfaces estables del corte

1. `load_territory(id) -> Territory` es el único punto de carga de un pack en
   Labs. Rechaza rutas absolutas, traversal y bbox mal ordenadas.
2. `Territory.layers` es la autoridad runtime para localizar capas. Sustituye
   cuatro mapas hardcoded que divergían en servicio, evals, evidence e
   isócronas.
3. `retriever-config.json` versiona el par modelo/calibración. Producción elige
   `e5large`; MiniLM permanece como referencia reproducible.
4. `/search` declara el método real (`retriever`, `reranked`) y añade
   `territory` + `territory_version`. Cada resultado conserva `why` y `data`.
5. MCP conserva ese contexto y adapta rutas sin geometría pesada, manteniendo
   duración, distancia, evidence, confidence y limitations del API.

El manifiesto Labs es configuración de ejecución, no un segundo schema de
entidad. La fuente de verdad de contratos normalizados sigue en
`emap-next/packages/schemas`; una futura convergencia debe hacer que el pack
Labs referencie esos contratos, no copiarlos.

## Deuda explícita

- El proceso del servicio carga un territorio por `EMAP_TERRITORY`; todavía no
  sirve Euskadi y Madrid simultáneamente.
- `confidence` es hoy una etiqueta de frescura o un score de categoría, no una
  probabilidad calibrada de respuesta completa.
- `answerable` no existe como objeto formal; `/search` usa `abstained`.
- Temporal, realtime y routing no se agregan todavía bajo un response contract
  Intelligence común.
- La telemetría existente no mide por fuente, abstención ni degradación
  cross-territory.
- `FastAPI.on_event` emite aviso de deprecación; no bloquea correctness y queda
  fuera de este cambio P0/P1.

## Decisiones de no construcción

No se añadió vector DB, base de datos, LLM, reranker, microservicio ni chatbot.
El volumen actual se resuelve en memoria y el reranker eliminado no estaba
conectado al runtime, añadía una descarga de 1,1 GB y su licencia no comercial
no era adecuada para producto.
