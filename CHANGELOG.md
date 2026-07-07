# Changelog — EMAP Labs

Formato basado en [Keep a Changelog](https://keepachangelog.com/). Las versiones
`vX.Y` etiquetan releases de datasets/artefactos publicables.

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
