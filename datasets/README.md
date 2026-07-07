# datasets

Pipelines de datasets propios de labs (roadmap L0+). Primer candidato:
**barrios** (límites de barrios de Bilbao + municipios de Bizkaia), la
unidad de agregación de señales que falta.

Convención: cada pipeline es un script reproducible que produce un dataset
con los 6 metadatos (licencia, versión, fecha, fuente, calidad, cobertura)
y se registra en el manifest de `../emap-next` vía `data-catalog` mientras
emap sea su consumidor.
