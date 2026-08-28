# Changelog — EMAP Labs

Formato basado en [Keep a Changelog](https://keepachangelog.com/). Las versiones
`vX.Y` etiquetan releases de datasets/artefactos publicables.

## [v0.3.0-rc.1] — 2026-08-29

Prerelease de validación multi-territorio de EMAP Intelligence/Core.

### Añadido
- Registro territorial versionado para Euskadi y Madrid, consumido por servicio,
  evals, frescura y contratos de respuesta sin ramas hardcoded por ciudad.
- Primer adapter oficial de Madrid: 2.306 fuentes de agua municipales con
  estado operativo, procedencia de coordenadas, checksum, cobertura y calidad.
- EMAPBench Madrid dev: 18 consultas geográficas, semánticas, de atributos,
  abstención y adversariales.
- Perfiles reproducibles de retrieval (`minilm`, `mpnet`, `e5large`) y gates CI
  separados para development y held-out manual.
- Contratos MCP que conservan territorio, método, limitaciones y atribución de
  la respuesta de Core.

### Cambiado
- El dataset canónico de Madrid se genera en `emap-next/data/processed`; el
  snapshot de `evals/data` queda como copia autocontenida de CI.
- El reranking se declara inactivo cuando no existe; no se atribuye una mejora
  al componente sin evidencia controlada.
- El builder de releases acepta semver/fecha, incorpora Madrid y genera tarballs
  con metadatos deterministas.

### Verificado
- Madrid dev: baseline 77%, semantic MiniLM 83%, hybrid MiniLM 88%.
- Euskadi dev e5-large: 89% ES y 84% EU.
- Euskadi held-out e5-large: 79% ES y 82% EU; baseline 58% ES y 51% EU.

### Limitaciones conocidas
- Madrid contiene una fuente y 18 casos dev; todavía no tiene held-out.
- El servicio selecciona un territorio por proceso, no ambos simultáneamente.
- El endpoint MCP objetivo requiere redeploy: devolvía 421 el 2026-08-28.
- Telemetría formal y response contract completo quedan fuera de esta RC.

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
