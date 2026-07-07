# EMAP Labs — Datasets v0.1

Primer release versionado de datasets de **EMAP Labs**, la capa de datos e
inteligencia detrás de [EMAP](https://emap-next.vercel.app). Territorio: Euskadi
(foco Bizkaia). Fecha: 2026-07.

Cada dataset se publica con **6 metadatos**: fuente, licencia, fecha de
actualización, checksum (SHA-256), cobertura y calidad (nº de registros y % de
campos vacíos). Ver `manifest.json` para los valores exactos.

## Contenido — 7 datasets, 12.732 registros

| Dataset | Registros | Fuente | Licencia |
|---|---:|---|---|
| **DEA (desfibriladores) de Euskadi** | 3.321 | Registro Vasco de DEA — Dpto. de Salud, Gobierno Vasco | Open Data Euskadi (CC BY 4.0) |
| Fuentes de agua potable | 6.278 | OpenStreetMap (Overpass) | ODbL 1.0 |
| Aseos públicos | 696 | OpenStreetMap (Overpass) | ODbL 1.0 |
| Aparcamientos | 641 | OpenStreetMap (Overpass) | ODbL 1.0 |
| Aparcabicis | 1.432 | OpenStreetMap (Overpass) | ODbL 1.0 |
| Playas | 217 | OpenStreetMap + Open Data Bizkaia (DFB) | ODbL 1.0 / CC BY 4.0 |
| **Barrios / límites administrativos de Bizkaia** | 147 | OpenStreetMap (Overpass) | ODbL 1.0 |

Barrios = 113 municipios + 8 distritos + 26 barrios de Bilbao (GeoJSON con
nombres oficiales ES/EU). El resto son POIs con `lat`/`lon`, nombre ES/EU,
categoría y tags.

## Formato

- `manifest.json` — índice con los 6 metadatos por dataset.
- `data/*.json` — los datasets. Barrios en **GeoJSON** (`features[]`); el resto
  en JSON con `pois[]` (`{source, updated, pois}`).

## Uso y atribución

- **OpenStreetMap (ODbL 1.0):** al usar o redistribuir hay que atribuir
  "© OpenStreetMap contributors" y mantener la licencia ODbL en obras derivadas.
- **DEA — Open Data Euskadi (CC BY 4.0):** atribuir al Registro Vasco de DEA
  (Dpto. de Salud, Gobierno Vasco). Dato de emergencia: **puede estar
  desactualizado**; no sustituye a fuentes oficiales en una urgencia.
- **Playas / Open Data Bizkaia:** atribución a la Diputación Foral de Bizkaia.

## Reproducibilidad

Regenerable con `python releases/build_release.py` desde el repo, que lee los
datasets fuente de `../emap-next` y recalcula checksums y calidad.
