# Candidatos de Open Data Euskadi — research 2026-07-08

Barrido del catálogo completo (4.962 datasets, `datasets.json` del propio
portal) buscando nichos que conviertan **abstenciones del corpus en
respuestas** y abran capas nuevas. Licencias: Open Data Euskadi publica en
CC-BY 4.0 salvo indicación — verificar por dataset al ingerir.

## P1 — desbloquean casos del corpus (ingerir primero)

| Dataset | Desbloquea | Notas |
|---|---|---|
| **Farmacias y Botiquines de Euskadi** | `ho-farmacia-guardia` (ubicaciones; las guardias pueden requerir fuente COF aparte) | georreferenciado |
| **Censo de instalaciones deportivas de Euskadi** | `ho2-eu-igerilekua` (piscinas), frontones, polideportivos — categoría "deporte" entera | el censo oficial GV |
| **Restaurantes, asadores, sidrerías, bodegas y bares de pintxos de Euskadi** | `asp-pintxos-casco`, `ho2-menu-del-dia` (ubicaciones; precios no), y media categoría "comer" del futuro places | serie turismo |
| **Hoteles de Euskadi** + **Alojamientos turísticos** + **Albergues** + **Alojamientos rurales** | `ho-hotel-barato` (ubicaciones) | serie turismo |
| **Campings de Euskadi** | `ho2-autocaravana` (parcial — campings admiten AC; áreas AC puras quizá municipales) | GeoJSON confirmado |
| **Paradas de taxi** (catálogo: `catalogo/-/paradas-taxi/`; + Donostia municipal) | `ho2-taxi` | cobertura por verificar (¿solo capitales?) |

## P2 — capas nuevas de valor directo

| Dataset | Para qué |
|---|---|
| **Espacios naturales y playas de Euskadi** (turismo) | categoría "verde/naturaleza" — `asp-zona-verde-getxo`, `asp-parque-sombra` (parcial) |
| **Bibliotecas Públicas de Euskadi** | plan de lluvia (`asp-plan-lluvia` parcial), capa servicios |
| **Red de senderos por Urdaibai** / **GR 12 Sendero de Euskal Herria** / itinerarios | vertical "descubrir" a pie, complementa bidegorris |
| **Oficinas de turismo / recursos turísticos** | explain-place en zonas turísticas |
| **Red de Espacios Libres de Humo** | curiosidad diferencial (parques sin humo) — nicho puro |

## P3 — vigilar / requiere trabajo extra

- **Áreas de autocaravanas puras**: no aparecen como dataset GV — buscar en
  portales forales/municipales (Bizkaia.eus, ayuntamientos costeros).
- **Wifi público**: no hay dataset GV; Pamplona lo tiene — pedir por
  transparencia o OSM (`internet_access=wlan`).
- **Radares / aforos de tráfico y bici**: no en GV; los aforos de bici de
  Bilbao existían en su portal municipal — revisitar Bilbao Open Data.
- **Guardias de farmacia** (horarios vivos): COF de Bizkaia — scraping o
  acuerdo; el dataset GV da las ubicaciones.

## Estado de ingestión

**2026-07-08: pipeline `euskadi-places/build.py` EJECUTADO — 7.568 POIs**:
pharmacy 843 (sin titulares — ética), sports 4.677 (173 piscinas), food 716,
lodging 849, hostel 82, camping 27, nature 60, library 314. Salida en
`emap-next/data/pois-euskadi/`. Falta: registrar en manifest, capas en el
retriever, voltear abstenciones del corpus, re-medir, servicio VPS.
Paradas de taxi: pendiente (dataset municipal, otro patrón).

## Plan de ingestión propuesto (siguiente sprint de datos)

1. Pipeline `datasets/euskadi-places/build.py` (patrón defib): descarga la
   serie turismo+equipamientos (P1) → `emap-next/data/pois-euskadi/` →
   manifest con 6 metadatos → capas nuevas en retriever (`pharmacy`,
   `sports`, `food`, `lodging`, `taxi`) → **voltear los casos `answerable:
   false` correspondientes a `true`** (con radios verificados) → re-medir.
2. El corpus gana ~6 categorías nuevas → el benchmark L3 se vuelve más rico
   justo antes de publicarlo.
3. Ética: son establecimientos/equipamientos (infraestructura), no personas
   — compatible con ETICA-DATOS.md. Nada de reseñas/precios/rankings.

Fuentes: catálogo completo `opendata.euskadi.eus/contenidos/ds_general/
catalogo_datos_opendata/opendata/datasets.json` (4.962 entradas, revisado
2026-07-08) · [Open Data Euskadi](https://opendata.euskadi.eus/catalogo-datos/) ·
[paradas de taxi](https://opendata.euskadi.eus/catalogo/-/paradas-taxi/) ·
[Moveuskadi](https://opendata.euskadi.eus/catalogo/-/moveuskadi-datos-de-la-red-de-transporte-publico-de-euskadi-operadores-horarios-paradas-calendario-tarifas-etc/)
