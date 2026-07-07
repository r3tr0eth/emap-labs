# evals

Corpus dorados y evaluación del sistema semántico (roadmap L1/L3).

- `semantic-golden-v0.yaml` — 50 casos (nearest/attribute/transit/semantic +
  robustez) con anclas y nombres verificados contra los datasets de
  `../emap-next` el 2026-07-07. **Borrador**: euskera pendiente de curación
  humana; objetivo 75–100 casos antes de iterar el retriever.

Los casos `answerable: false` son deliberados: miden que el sistema
reconozca sus límites en vez de inventar resultados (no se finge).

El harness que ejecute este corpus contra el retriever (y en L3 contra
varios modelos midiendo precisión/latencia/coste) vivirá aquí.
