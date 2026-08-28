# Madrid Labs — shortlist de fuentes oficiales

**Revisión:** 2026-08-28. **Estado:** primer vertical slice ejecutable; una
fuente P0 aceptada y seis pendientes. Solo se consideran fuentes primarias del
organismo propietario. “Seleccionada” significa que entra en el diseño del
pack; “aceptada” exige descarga de muestra, adapter, validación de
licencia/freshness y casos development.

## Por qué Madrid está en el mapa pero no en Labs

`emap-next` ya resuelve Madrid mediante tres caminos independientes del índice
Labs: geocoder nacional con hitos Madrid (`packages/routing/.../geocode.py` y
`build-suggest-catalog.py`), routing de carretera con fallback nacional y un
grafo OTP Euskadi+Madrid construido con GTFS (`scripts/hetzner-otp-madrid.sh`,
golden `test_golden_madrid_live.py`).

Labs, en cambio, solo cargaba 22 rutas de ficheros Euskadi. El registro común
ya carga `regions/madrid/region.yaml`, pero Madrid v0.1 contiene únicamente la
capa oficial de fuentes. El basemap y OTP no crean automáticamente un índice
geo-semántico: cada fuente aún necesita adapter, manifest y evaluación.

## Vertical slice Madrid v0.1 verificado

La fuente de fuentes de beber pasa a **aceptada** con evidencia reproducible:

- adapter: `datasets/madrid-fountains/build.py`;
- salida normalizada: `evals/data/madrid/pois/fountains.json`;
- 2.306 POIs válidos, 271 coordenadas recuperadas desde ETRS89/UTM 30N y un
  registro oficial descartado por carecer de coordenadas utilizables;
- 2.261 operativos, 43 fuera de servicio y 2 cerrados temporalmente;
- `source_updated`, URL, licencia, atribución, SHA-256, conteos de estado y
  procedencia de coordenada incluidos en el artefacto;
- corpus development de 18 casos, sin abrir held-out;
- resultados: baseline 14/18 (77%), semantic MiniLM 15/18 (83%) e hybrid
  MiniLM 16/18 (88%). El híbrido conserva geografía 8/8 y constraints 3/3,
  pero todavía confunde “fuente tipográfica” y “fuente de la juventud”.

La fuente municipal es diaria, pero su propio catálogo advierte que el estado
de servicio puede variar. Por ello Madrid fija un SLA de 2 días y no interpreta
`OPERATIVO` como disponibilidad garantizada en tiempo real.

## Siete fuentes seleccionadas

| Fase | Dominio / capa | Fuente oficial y formato | Actualización / licencia | Reutilización | Riesgo antes de aceptar |
|---|---|---|---|---|---|
| P0 | Transporte (`metro`, `cercanias`, bus genérico) | [CRTM Datos Abiertos](https://transparencia.crtm.es/presupuestos-contratos-y-gastos/datos-abiertos/?lang=es): GTFS, SHP, KML, CSV y API GeoJSON | GTFS estático; [licencia CRTM](https://www.crtm.es/licencia-de-uso) permite uso comercial/no comercial, transformación y combinación con atribución | Reutiliza parser GTFS, geo, routing y capas de paradas; el feed ya alimenta OTP | No duplicar la copia operativa: definir un snapshot único y su hash. La taxonomía de bus debe ser genérica, no `bilbobus`/`bizkaibus` |
| P0 | Aparcamiento (`parking`) | [Aparcamientos públicos municipales](https://datos.madrid.es/dataset/202625-0-aparcamientos-publicos): CSV, JSON, XML, RDF y GEO | Diaria; CC BY 4.0; responsable municipal de movilidad | Adapter de POI y categoría `parking` existentes | Normalizar coordenadas/direcciones y distinguir rotación, residentes y disuasorio sin afirmar disponibilidad |
| P1 | Disponibilidad de parking (`parking.realtime`) | [Ocupación de aparcamientos rotacionales](https://datos.madrid.es/dataset/50027-0-aparcamientosocupacionyservicios/downloads): API/WSDL | Tiempo real; recurso API CC BY 4.0 | Enriquece las mismas entidades parking; prueba temporal/realtime | Cobertura voluntaria y parcial; necesita entity resolution robusta contra el inventario estático y timestamp por observación |
| P0 | Movilidad eléctrica (`ev`) | [Recarga rápida de acceso público](https://datos.madrid.es/dataset/208979-0-puntos-recarga-historico): CSV, SHP, WMS e histórico | Mensual; CC BY 4.0; Geoportal municipal | Categoría `ev`, filtros de potencia/conector y evidence existentes | El inventario incluye operadores privados comunicados voluntariamente: completeness no estimable y operatividad no garantizada |
| P0 | Servicio urbano verificable (`fountains`) | [Fuentes de agua para beber](https://datos.madrid.es/dataset/300051-0-fuentes/downloads): JSON, CSV y XML por año | Diaria; CC BY 4.0 | Reutiliza `fountains`, demo nearby y abstención por estado | Elegir siempre el recurso del año corriente; conservar `OPERATIVO/NO OPERATIVO/CERRADA TEMPORALMENTE` y fecha de toma |
| P0 | Movilidad sostenible (`bikepark`) | [Bici. Aparcabicis](https://datos.madrid.es/dataset/205099-0-aparca-bicis): recursos geográficos y tabulares por año | Diaria; CC BY 4.0 | Reutiliza `bikepark` sin categoría nueva | Cobertura declarada solo para vía pública; documentar exclusiones de instalaciones y parques |
| P1 | Tráfico verificable (`cameras`) | [Tráfico. Cámaras](https://datos.madrid.es/dataset/202088-0-trafico-camaras/information): KML + imagen periódica | Tiempo real; imagen cada cinco minutos; CC BY 4.0 | Reutiliza `cameras`, evidence y freshness | La cámara confirma estado visual, no velocidad ni causalidad; cache corto y abstención si imagen/timestamp fallan |

La primera fuente P0 ya está integrada. La siguiente entrega debe escoger una
segunda capa P0 —preferentemente parking o aparcabicis— y mantener el mismo
contrato; las dos P1 se añaden después de resolver identidad y tiempo.

## Fuente deliberadamente no seleccionada

El GBFS de BiciMAD sería una gran demo realtime, pero el [metadato oficial de
EMT](https://datos.emtmadrid.es/dataset/70341916-cf8e-42f2-9c23-797539694bb4/resource/68dee117-c5ee-42d1-814a-60e1ebd8387a/download/metadatos_gbfs_bicimad.pdf)
declara **Creative Commons Non-Commercial**. No entra en el pack de producto
mientras EMT no confirme por escrito términos compatibles. No se sustituirá
por un mirror no oficial para eludir la licencia.

## Gate de aceptación por fuente

1. URL/respuesta recuperable sin credencial personal ni scraping de UI.
2. Licencia y atribución guardadas en el manifest.
3. Adapter idempotente: input raw versionado → JSON normalizado determinista.
4. `source_updated`, `generated`, hash y conteo presentes.
5. Coordenadas WGS84 y bbox Madrid validadas; duplicados cuantificados.
6. Casos development positivos, ambiguos e imposibles; ningún held-out visible
   durante adapter/calibración.
7. Evidencia de paridad: el retriever y response contract no contienen ramas
   Madrid, solo configuración y adapters de borde.

## Decisión de implementación

No crear un “pipeline Madrid” separado. El manifest, runner, retrieval,
freshness y dashboard v0.1 ya son compartidos; solo el adapter del formato
municipal permanece en el borde. El bus de Madrid fuerza una mejora común:
capas de red genéricas con operador/route como atributos, en vez de añadir
otro nombre de operador al core semántico.
