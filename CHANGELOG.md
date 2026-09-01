# Changelog — EMAP Labs

Formato basado en [Keep a Changelog](https://keepachangelog.com/). Las versiones
`vX.Y` etiquetan releases de datasets/artefactos publicables.

## [v0.3.0-rc.1] — 2026-08-29 · revisado 2026-08-31

Prerelease de validación multi-territorio de EMAP Intelligence/Core. La
sección original (corte 2026-08-29: 1 adapter Madrid, 18 casos dev, un
territorio por proceso) quedó superada por el corte multi-territorio del
30/31-ago; se revisa in place porque la RC no está tagueada aún.

### Añadido
- `RuntimeRegistry` inmutable sirviendo Euskadi y Madrid simultáneamente en
  una instancia: resolución por request (id o bbox), sin fallback silencioso,
  errores tipados (404/422) y `/healthz` por territorio.
- 3 adapters oficiales de Madrid: `fountains`, `parking`, `bikepark`
  (9.767 POIs con estado, procedencia, checksum, cobertura y calidad).
- EMAPBench Madrid v0.2.0: 60 casos dev + 19 held-out **sellados**
  (`evals/madrid-heldout-seal.json`, sha256 del corpus, calibración excluida).
- Perfiles reproducibles (`minilm`, `mpnet`, `e5large`) y gates CI separados:
  dev en push/PR; held-out solo manual (`run_heldout`, y `run_heldout_madrid`
  como medición única), con resultados persistidos por artifact.
- Response Contract v1 con validación automática (`validate_response()` en
  cada build), estados ANSWERED/NO_RESULT/ABSTAINED/UNSUPPORTED, limitación
  `STALE_EVIDENCE` en respuestas con evidencia stale y errores con
  `schema_version`.
- Suite Labs completa en CI: 46 tests (contratos, runtime, MCP, aislamiento
  concurrente), deps pinneadas, `conftest.py` (sin dependencia de orden) y
  skip de MCP prohibido en CI.
- `evals/run.py` registra `corpus_sha256` y latencia agregada del run
  (avg/max/total), y rechaza
  con mensaje claro un idioma no soportado por el corpus del territorio.

### Cambiado / corregido (revisión 2026-08-31 / 2026-09-01)
- **Fix del harness de evals (2026-09-01)**: `SemanticEncoder` ignoraba
  `EMAP_RETRIEVER_PROFILE`, de modo que todo resultado "e5large" del harness
  había ejecutado MiniLM con etiqueta falsa (los artefactos declaraban además
  la calibración del perfil pedido, no la ejecutada). Producción no se vio
  afectada (el factory pasa el perfil explícito). Desde el fix, la `config`
  del artefacto sale del encoder que ejecutó, con test de regresión; los
  ficheros e5large mal etiquetados del 2026-09-01 se descartaron y los del
  2026-08-05 quedan invalidados como medición del perfil.
- Telemetría: `no_result`, `abstained` y `unsupported` son contadores
  separados por `answer_status`; `source_failure` tiene disparador real
  (resultados sin documento de fuente).
- Freshness: el fallback de SLA es neutro por territorio — el SLA del
  territorio del proceso ya no contamina a los demás.
- MCP `search_places` propaga `took_ms` (antes se perdía solo ahí).
- `/accessible-pois` devuelve `count` real (antes 0 hardcodeado).
- El reranking se declara inactivo cuando no existe; no se atribuye una mejora
  al componente sin evidencia controlada.
- El builder de releases acepta semver/fecha, incorpora Madrid y genera tarballs
  con metadatos deterministas.

### Verificado
- Corte dev 2026-08-31: Madrid baseline 46/60 (76%), hybrid MiniLM 53/60
  (88%); Euskadi baseline 58/82 ES y EU (70%), hybrid MiniLM 64/82 ES (78%) y
  60/82 EU (73%).
- Primera medición real de hybrid E5 Large (2026-09-01, VPS): Euskadi 70/82
  ES (85%) y 68/82 EU (82%) — +7/+9 pp sobre MiniLM —; Madrid 53/60 (88%);
  challenge 30/47 ES (63%) y 31/47 EU (65%) vs 26/47 y 28/47 de MiniLM.
  Gates de CI fijados con esta evidencia: Madrid 85; Euskadi 80/78 (por
  encima del rendimiento MiniLM, para que una regresión de modelo se detecte
  sola).
- Held-out (últimos ficheros registrados): Madrid baseline 13/19 (68%), hybrid
  MiniLM 14/19 (73%); Euskadi baseline ES 17/29 (58%), hybrid MiniLM 18/29 ES
  y EU (62%).
- Serving multi-territorio verificado en producción (2026-08-31): `/healthz`
  con 2 territorios, contrato v1 completo en search/nearby de ambos,
  `territory=paris` → 404 explícito, MCP público vivo.
- Suite completa 46/46 en verde en un solo entorno local y en simulación del
  runner de CI (sin hermano en imports; hermano + jsonschema para los schemas).

### Limitaciones conocidas
- E5 Large solo tiene medición en development y challenge; su held-out
  (Euskadi e5 y Madrid e5) sigue pendiente del job manual, y los umbrales
  held-out de evals.yml (70/68) proceden de la era del bug — revisarlos
  conscientemente antes de la ejecución única.
- En Madrid dev, e5 responde un caso `unsupported` donde MiniLM se abstenía
  (empate 53/60 con distinto reparto): la abstención del modelo grande merece
  vigilancia.
- Madrid es solo ES y 3 capas; sus datos en prod dependen de re-ingesta
  (SLA 2 días) y estaban stale el 2026-08-31.
- Telemetría sin dimensión endpoint/tool, sin percentiles y sin persistencia;
  el servidor MCP no registra telemetría.
- Confidence no agrega los factores al score; sin factor geográfico ni
  detección de conflicto de evidencia.
- El tarball `emap-labs-datasets-v0.3.0-rc.1.tar.gz` es del corte 2026-08-29
  (sin parking/bikepark): regenerar antes de taguear.

## [v0.1] — 2026-07-07

Primer release versionado de datasets — **cierra la fase L0** del roadmap.

### Añadido
- **Release de datasets v0.1**: 7 datasets de Euskadi (12.732 registros) con los
  6 metadatos (fuente, licencia, fecha, checksum SHA-256, cobertura, calidad):
  DEA (3.321), fuentes (6.278), aseos (696), aparcamientos (641), aparcabicis
  (1.432), playas (217) y barrios de Bizkaia (147).
- `releases/build_release.py` — build reproducible que lee los datasets de
  `../emap-next` y genera `releases/v0.1/manifest.json` + tarball descargable.
- `releases/RELEASE-NOTES.md` — contenido, procedencia y atribución.

### Contexto (ya existente antes de este tag)
- L0.1: `coverage` + CLI `quality` en `data-catalog` (emap-next).
- L0.2: dataset de barrios (`datasets/neighborhoods/build.py`, OSM/ODbL).
- Corpus dorado v0 de búsqueda semántica (`evals/semantic-golden-v0.yaml`, 50 casos).
