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

## Resultados (la cifra a batir)

| Retriever | ES | EU | Fecha |
|---|---|---|---|
| baseline-keywords-geo | **45/47 (95%)** | 44/47 (93%) | 2026-07-07 |

Fallos restantes del baseline: los casos que exigen entender intención sin
palabra-clave (`metro-hasta-playa`, `ultima-estacion-l1`) — exactamente el
margen que el retriever semántico de L1 debe cerrar.

Huecos de datos detectados (v0): cargadores EV fuera de Bilbao (falta fuente
OCM/IBIL), tags `fee=no` de aparcamiento escasos en OSM fuera de Bilbao.

## Advertencia honesta sobre el 95%

El corpus v0 es **amable con keywords**: las consultas contienen la palabra de
la categoría ("fuente", "aseo"…) porque se redactaron mirando los datasets. Un
baseline léxico brilla ahí. La ampliación a 75–100 casos debe añadir
**paráfrasis sin palabra-clave** ("dónde relleno el bidón", "me urge un sitio
donde cambiar al bebé", "cargar el patinete") — ahí es donde los embeddings
tienen que ganarse el puesto, y donde el baseline debería caer con estrépito.
Si el semántico no supera claramente al baseline en esas, no se despliega.
