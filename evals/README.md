# evals

Corpus dorados y harness de evaluación del sistema semántico (roadmap L1/L3).

## Ejecutar

```bash
./.venv/bin/python evals/run.py --retriever baseline --lang es
./.venv/bin/python evals/run.py --retriever hybrid --profile minilm --lang eu
```

Lee los datasets desde `../emap-next` (solo lectura), corre el corpus contra el
retriever y guarda `evals/results/<retriever>-<lang>-<fecha>.json` para comparar
en el tiempo. `--output-dir /tmp/...` permite una verificación aislada. El
retriever recibe solo consulta + anchor — **nunca ve `expected`**.

## Ficheros

- `semantic-golden-v0.yaml` — 162 casos
  (nearest/attribute/transit/semantic + robustez), anclas y nombres
  verificados contra datos reales. Los
  `answerable: false` miden abstención (no inventar); los `known_gap` marcan
  casos irresolubles por falta de datos — se reportan como inventario de huecos,
  no como fallo del retriever.
- `baseline.py` — retriever keywords ES/EU + filtro geográfico, sin embeddings.
  Es la cifra a batir.
- `landmarks.yaml` — anclas tipo landmark → coordenadas fijas (entrada del
  caso, no parte de la respuesta).
- `run.py` — el harness.
- `retriever-config.json` — perfiles versionados que unen modelo, threshold y
  tie-window; evita calibraciones implícitas distintas en local/CI/prod.

## Resultados

Corpus actual: **162 casos** sobre 22 capas. Se divide en **dev 85**
(82 puntuables + 3 `known_gap`), **held-out 29** sellados y **challenge 48**
(47 puntuables + 1 gap). El runner usa dev por defecto. CI usa dev; held-out
solo se habilita manualmente para una decisión final y NUNCA para calibrar.

Verificación development del 2026-08-27 tras introducir el registro
territorial y fijar FastEmbed 0.8.0:

| Retriever | dev ES | dev EU |
|---|---:|---:|
| baseline-keywords-geo | 61/82 (74%) | 59/82 (71%) |
| hybrid MiniLM · perfil `minilm` | 67/82 (81%) | 61/82 (74%) |

El perfil `e5large` queda configurado con τ=0.80/tie=0.01 y gateado en CI. No
se reejecutó localmente el 2026-08-27: su artefacto ONNX de 2,24 GB no cabía en
el volumen (2,13 GB libres). No se ejecutó held-out para suplir esa ausencia.

La siguiente tabla es **histórica** (2026-08-05), conservada para trazabilidad;
no equivale a una medición nueva del corpus actual:

| Retriever | dev ES | **held-out ES** | dev EU | **held-out EU** |
|---|---|---|---|---|
| baseline-keywords-geo | 74% | **60%** | 71% | 62% |
| hybrid (MiniLM) — legado | 76% | 58% | 71% | 63% |
| **hybrid (e5-large)** — prod | **76%** | **73%** | **71%** | **71%** |

**Ampliación 2026-07-09 (euskadi-places)**: +8 capas (farmacia, biblioteca,
deporte, restaurantes, hotel, albergue, camping, espacios naturales — 7.568
POIs de Open Data Euskadi) y +16 casos dev (`ep-*`). Tres hallazgos:

1. **MiniLM no escala de 13 a 21 categorías**: en held-out ES el híbrido
   perdía contra el baseline (58% < 60%) — el criterio de despliegue se rompía.
   **Resuelto 2026-08-05 con e5-large**: el híbrido en 22 capas alcanza 73% held-out
   ES (+15) y 71% held-out EU (+8). Prod desplegado con e5-large y 22 capas.
2. **La declinación vasca rompía `strip_location`**: "Moyuatik gertu" no
   casaba con el anchor "Moyua" y la cláusula locativa entera ensuciaba el
   embedding EU (por eso capas basura robaban el top-1). Arreglado
   (prefijo + locativos pospuestos); el nombre declinado como resultado
   ("Itxinako biotopo babestua") sigue abierto — caso `ep-sem-biotopo-itxina`.
3. **Recalibración en dev** (τ 0.45→0.50, tie 0.08→0.03): con 21 categorías
   el tie-window ancho colaba capas a 0.08 del top que ganaban por cercanía.
   Elegido por paridad ES/EU sobre barrido completo.

**Casos mendi (2026-07-10, `md-*`)**: la capa `peaks` (1.130 cimas) entra
SOLO por keywords — añadirla a la etapa semántica con MiniLM repetiría la
degradación medida el 07-09. El caso `md-sem-subir` ("subir al Pagasarri",
sin sustantivo de categoría) queda como medición del hueco: hoy falla en
ambos idiomas por diseño (en EU MiniLM lo clasifica como hostel), y es un
objetivo explícito de L3.

Además la capa `nature` viene mezclada de origen (41 playas + 19 espacios
naturales reales) — separar zonas de baño es mejora pendiente del pipeline.
Resultados históricos del corpus de 117 casos (13 capas): `results/` y git.

**Euskera validado con Itzuli (2026-07-08)**: las 112 queries no-robustez se
cotejaron con el traductor neuronal del Gobierno Vasco — 27 idénticas, 38
adoptadas de Itzuli, 6 ajustes combinados, resto mantenidas con motivo
(Itzuli también falla: candar→txanda, chapuzón→txapligu, formas subordinadas
no-query). Hallazgo: con euskera correcto TODOS los números EU bajan 1-3
pts y el híbrido pasa a EMPATAR con el baseline en held-out — el euskera
artificial original inflaba la medición. La brecha EU real es mayor:
argumento central del benchmark L3.

(Held-out ampliado 2026-07-08 a 53 casos con la tanda H2, deliberadamente más
dura: la ventaja del híbrido se estrecha a +1/+2 pts. Sigue ≥ baseline en
ambos idiomas — el criterio de despliegue se mantiene por la mínima — pero el
margen fino marca el objetivo de L3: mejor etapa semántica (embeddings
mejores o clasificador LLM). Patrón de fallo dominante: parking/bikepark
absorben consultas ambiguas; 2 abstenciones con fuga (taxi, autocaravana).
Resultados históricos con el held-out de 29 casos en results/.)

(MiniLM multilingüe vía FastEmbed 0.8.0; perfil actual `minilm` τ=0.50,
tie=0.03. Producción selecciona el perfil versionado `e5large` τ=0.80,
tie=0.01 desde `service/deploy.sh`.)

## Benchmark L3 — embeddings multilingües (2026-07-24)

fastembed 0.8 no trae **BGE-M3** ni **Qwen3** (sólo variantes en/zh de BGE) —
los objetivos originales del roadmap esperan `sentence-transformers` nativo en
la caja de 8 GB. La vía multilingüe viable HOY: MiniLM-L12 (384d, actual),
mpnet-base (768d) y **multilingual-e5-large** (1024d). Cada modelo se
recalibró en dev (barrido τ/tie, criterio de paridad ES/EU) y se corrió
held-out **una sola vez** con su config ganadora:

| Modelo (config dev) | dev ES | dev EU | **held-out ES** | **held-out EU** |
|---|---|---|---|---|
| baseline keywords+geo | 74% | 71% | 60% | 62% |
| MiniLM-L12 · τ0.60/t0.02 | 80% | 76% | 60% | 66% |
| mpnet-base · τ0.65/t0.02 | 79% | 73% | 64% | 66% |
| **e5-large · τ0.80/t0.01** | **76%** | **71%** | **73%** | **71%** |

Hallazgos:

1. **Un τ fijo no transfiere entre modelos.** e5 concentra sus cosenos en una
   banda alta y estrecha (dev ES, casos que llegan a la semántica:
   answerable=True min 0.79 / False max 0.81): con el τ=0.50 heredado de
   MiniLM la abstención de e5 queda MUERTA (resultado idéntico de τ=0.40 a
   0.70 — sólo el tie mueve la aguja). Recalibrado a **τ=0.80**, justo entre
   las dos nubes, e5 pasa de mediocre a mejor de todos. La calibración es
   propiedad del par (modelo, corpus), no del corpus.
2. **e5-large recupera y supera el criterio de despliegue roto.** Los dos
   hallazgos que rompían L1 se cierran: el híbrido ya no pierde el held-out ES
   contra el baseline (58→**75%**, +15) y la brecha EU se invierte
   (66→**81%**, +15). Generaliza de dev a held-out sin colapsar (88/84 →
   75/81); en held-out el EU incluso supera al ES.
3. **mpnet no justifica su tamaño** (3× MiniLM): empata o mejora por poco y no
   cierra EU. e5-large (2.24 GB) es el salto real, y es un modelo abierto
   (MIT) sin lock-in.

**Estado de despliegue (2026-08-05)**: e5-large está **desplegado en producción**
con 22 capas (13 OSM + 8 euskadi-places + peaks), calibración τ=0.80/tie=0.01,
EMAP_EMBED_MODEL=intfloat/multilingual-e5-large. VPS de 16 GB → sin cuello de
botella. El benchmark deja el modelo elegido y su calibración listos.

Modelo y calibración se seleccionan juntos mediante
`EMAP_RETRIEVER_PROFILE` o `--profile`; los overrides de laboratorio
`EMAP_SIM_TAU`/`EMAP_TIE_WIN` siguen disponibles, pero cualquier modelo nuevo
debe registrar primero un perfil. Los resultados quedan en `results/` con
sufijo estable (`hybrid-e5large-eu-heldout-…json`).

**Criterio de despliegue** (histórico 2026-07-08, con 13 capas): el híbrido
seguía ≥ baseline en held-out en ambos idiomas. **Desde 2026-07-09 y hasta
2026-08-05, con 21 capas el criterio estaba roto en ES con MiniLM**. **Resuelto
2026-08-05**: e5-large recupera el criterio con 22 capas (73% ≥ 60% baseline en
ES, 71% ≥ 62% en EU). Desplegado en producción.

Lecciones del primer día de harness:

1. **Embeder POIs con su nombre = 13/60.** El nombre ahoga la señal de
   categoría. La arquitectura buena es dos etapas: clasificación semántica de
   categoría (con la cláusula de ubicación recortada) + búsqueda estructurada
   geo/atributos. Es la misma arquitectura que tendrá `/nearby` con pgvector.
2. **El euskera de MiniLM multilingüe es flojo**: el fallback semántico
   EMPEORA al baseline en EU (71% vs 75%). Cuantificar esto por modelo es
   exactamente el benchmark de L3 — nadie lo tiene para euskera.
3. Los umbrales (τ, tie-window) están **calibrados sobre este mismo corpus**:
   el resultado es optimista por construcción. La ampliación a 75–100 casos
   debe reservar un split held-out que no se use para afinar nada.
4. Las descripciones de categoría y las paráfrasis las escribió la misma
   persona; la validación real llegará con consultas de usuarios.

Huecos de datos detectados (v0): cargadores EV fuera de Bilbao (falta fuente
OCM/IBIL), tags `fee=no` de aparcamiento escasos en OSM fuera de Bilbao.

Criterio de despliegue: el semántico/híbrido solo entra en producción si
supera claramente al baseline en el corpus ampliado con held-out — en ambos
idiomas, no solo en español.
