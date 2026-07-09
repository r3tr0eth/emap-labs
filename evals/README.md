# evals

Corpus dorados y harness de evaluación del sistema semántico (roadmap L1/L3).

## Ejecutar

```bash
../emap-next/.venv/bin/python evals/run.py [--retriever baseline] [--lang es|eu] [-k 5]
```

Lee los datasets desde `../emap-next` (solo lectura), corre el corpus contra el
retriever y guarda `evals/results/<retriever>-<lang>-<fecha>.json` para comparar
en el tiempo. El retriever recibe solo consulta + anchor — **nunca ve `expected`**.

## Ficheros

- `semantic-golden-v0.yaml` — 50 casos (nearest/attribute/transit/semantic +
  robustez), anclas y nombres verificados contra datos reales. Los
  `answerable: false` miden abstención (no inventar); los `known_gap` marcan
  casos irresolubles por falta de datos — se reportan como inventario de huecos,
  no como fallo del retriever.
- `baseline.py` — retriever keywords ES/EU + filtro geográfico, sin embeddings.
  Es la cifra a batir.
- `landmarks.yaml` — anclas tipo landmark → coordenadas fijas (entrada del
  caso, no parte de la respuesta).
- `run.py` — el harness.

## Resultados

Corpus 133 casos sobre **21 categorías**: **dev** 79 (76 puntuables + 3
known_gap, usados para calibrar) y **held-out** 54 (secciones H y H2, prefijo
`ho-`; 53 puntuables + 1 known_gap; el runner los excluye por defecto —
`--split heldout` para correrlos, y NUNCA se calibra mirándolos).

| Retriever | dev ES | **held-out ES** | dev EU | **held-out EU** |
|---|---|---|---|---|
| baseline-keywords-geo | 73% | **60%** | 71% | 62% |
| **hybrid-keywords-then-semantic** | **81%** | 58% | 73% | **66%** |

**Ampliación 2026-07-09 (euskadi-places)**: +8 capas (farmacia, biblioteca,
deporte, restaurantes, hotel, albergue, camping, espacios naturales — 7.568
POIs de Open Data Euskadi) y +16 casos dev (`ep-*`). Tres hallazgos:

1. **MiniLM no escala de 13 a 21 categorías**: en held-out ES el híbrido
   pasa a PERDER contra el baseline (58% < 60%) — el criterio de despliegue
   se rompe. **Prod sigue en 13 capas con su calibración fijada por env en
   `service/deploy.sh`**; el upgrade de embeddings (L3) deja de ser mejora
   y pasa a ser bloqueador para activar las capas nuevas.
2. **La declinación vasca rompía `strip_location`**: "Moyuatik gertu" no
   casaba con el anchor "Moyua" y la cláusula locativa entera ensuciaba el
   embedding EU (por eso capas basura robaban el top-1). Arreglado
   (prefijo + locativos pospuestos); el nombre declinado como resultado
   ("Itxinako biotopo babestua") sigue abierto — caso `ep-sem-biotopo-itxina`.
3. **Recalibración en dev** (τ 0.45→0.50, tie 0.08→0.03): con 21 categorías
   el tie-window ancho colaba capas a 0.08 del top que ganaban por cercanía.
   Elegido por paridad ES/EU sobre barrido completo.

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

(MiniLM multilingüe vía fastembed; config actual τ=0.50, tie=0.03 — la
completa queda versionada en cada JSON de `results/`. Prod mantiene
τ=0.45/0.08 con 13 capas, fijada en `service/deploy.sh`.)

**Benchmark L3 — modelos de embedding probados (dev, híbrido):**

| Modelo | dev ES | dev EU | Nota |
|---|---|---|---|
| **MiniLM-L12 multilingual (actual)** | **86%** | **73%** | τ=0.45 |
| mpnet-base-v2 multilingual | 80% | 71% | recalibrado (barrido τ 0.35-0.50); PEOR pese a ser 3× más grande — descartado |
| BGE-M3 | — | — | objetivo del roadmap; no está en fastembed y no cabe en el Mac (2.3GB libres) → esperar caja 8GB |

Modelo y calibración ahora intercambiables por env (`EMAP_EMBED_MODEL`,
`EMAP_SIM_TAU`, `EMAP_TIE_WIN`) — la mecánica del benchmark está lista.

**Criterio de despliegue** (histórico 2026-07-08, con 13 capas): el híbrido
seguía ≥ baseline en held-out en ambos idiomas por la mínima y se mantuvo
desplegado. **Desde 2026-07-09, con 21 capas, el criterio está ROTO en ES**
(ver hallazgos arriba): prod permanece en la config de 13 capas y las capas
nuevas no se activan en producción hasta que una etapa semántica mejor
recupere el criterio — EL objetivo medible de L3.

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
