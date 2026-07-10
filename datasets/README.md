# datasets

Pipelines de datasets propios de labs (roadmap L0+). Primer candidato:
**barrios** (límites de barrios de Bilbao + municipios de Bizkaia), la
unidad de agregación de señales que falta.

Convención: cada pipeline es un script reproducible que produce un dataset
con los 6 metadatos (licencia, versión, fecha, fuente, calidad, cobertura)
y se registra en el manifest de `../emap-next` vía `data-catalog` mientras
emap sea su consumidor.

## Pipelines

- `neighborhoods/` + `neighborhood-scores/` — límites de Bizkaia y el
  índice de cobertura L2 (registrados en el manifest, `processed/`).
- `euskadi-places/` — 8 capas de Open Data Euskadi (~7.500 POIs:
  farmacias, bibliotecas, deporte, restaurantes, alojamiento, camping,
  espacios naturales) → `data/pois-euskadi/`. La capa nature filtra las
  playas de la fuente (duplican la capa beaches).
- `mendi/` — el vertical "el monte en transporte público", escala Euskadi
  (ES-PV; v0 era Bizkaia): `build.py` trae 2.825 cimas con nombre (OSM
  `natural=peak` → `peaks.json`) y 397 rutas señalizadas (`route=hiking`,
  solo metadatos → `routes.json`); `transit_cross.py` cruza cimas × 9
  redes de transporte (→ `processed/mendi/peaks-transit.json`, registrado
  en el manifest): **1.700 cimas con parada a ≤2 km** en línea recta (no
  ruta a pie — OTP dará el cómo-llegar real en L5).

Pendiente (emap-next): registrar las capas fuente de `data/pois-euskadi/`
en el manifest — hoy solo `processed/` está catalogado.
