# Error Corpus Schema

Formato para registrar fallos del retriever con ciclo de vida completo.
Cada entrada es un YAML file en `evals/errors/` que documenta un fallo
específico, su causa y su resolución.

## Filosofía

> Este bug apareció el 4 de septiembre y nunca volvió.

El error corpus no es solo un log: es **regression testing vivible**.
Cada entrada comprometida con un commit que la demuestra.

## Esquema

```yaml
# evals/errors/<retriever>-<date>-<slug>.yaml
id: e5large-2026-08-05-farmacia-centro-medico
status: open | fixed | wontfix | duplicate
severity: critical | major | minor
created: 2026-08-05
fixed: null  # fecha cuando se resuelva

query:
  text: "farmacia cerca de Moyua"
  lang: es
  lat: 43.263
  lon: -2.935

expected:
  layers: [pharmacy]
  within_m: 400

got:
  layers: [medical_center]  # lo que devolvió
  result_name: "Centro de Salud Moyua"

diagnosis: >
  La descripción de categoría "pharmacy" en semantic_local.py tiene
  demasiado peso de términos genéricos ("salud", "medicamentos") que
  solapan con "medical_center". El coseno es 0.72 para pharmacy vs 0.75
  para medical_center.

fix_rule: >
  Boost términos específicos de farmacia ("farmacéutico", "receta",
  "botica") en la descripción de categoría, o añadir anti-ejemplos de
  centros médicos.

fix_commit: null  # SHA cuando se aplique
related_cases:  # IDs de casos del corpus sintético afectados
  - ep-sem-medicinas
retriever: hybrid-e5large-rerank
model: intfloat/multilingual-e5-large
config:
  tau: 0.80
  tie: 0.01
  rerank: jina-reranker-v2-base-multilingual
```

## Ciclo de vida

1. **Detectado**: automáticamente (CI) o manualmente (usuario)
2. **Registrado**: `status: open`, `fix_commit: null`
3. **Diagnosticado**: se rellena `diagnosis` y `fix_rule`
4. **Arreglado**: `status: fixed`, `fix_commit: <sha>`, `fixed: <fecha>`
5. **Verificado**: CI corre el caso y confirma que ya no falla

## Tipos de severidad

- **critical**: devuelve categoría completamente equivocada (farmacia → fuente)
- **major**: categoría correcta pero POI equivocado o radio excedido
- **minor**: categoría correcta pero orden subjetivamente malo

## Directorio

```
evals/errors/
  open/       # bugs activos
  fixed/      # bugs resueltos (demostrables por CI)
  wontfix/    # decisiones conscientes (documentadas)
```

## Integración CI

El workflow `evals.yml` incluye un paso `regression`:

```bash
python evals/error_corpus.py --check
```

Que falla si:
- algún error `fixed` vuelve a fallar
- algún error `open` supera 30 días sin diagnóstico
