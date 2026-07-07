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

## Resultados (corpus 63 casos: 60 puntuables + 3 known_gap)

| Retriever | ES | EU | Nota |
|---|---|---|---|
| baseline-keywords-geo | 46/60 (76%) | 45/60 (75%) | falla las paráfrasis sin keyword (sección F), como debe |
| semantic-minilm-2stage | 38/60 (63%) | — | gana en paráfrasis (17/23 vs 11/23) pero pierde en transporte fino |
| **hybrid-keywords-then-semantic** | **51/60 (85%)** | 43/60 (71%) | keywords primero, embeddings de fallback — candidato a producción en ES |

(2026-07-07, MiniLM multilingüe vía fastembed, τ=0.45, tie=0.08 — config
completa versionada en cada JSON de `results/`.)

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
