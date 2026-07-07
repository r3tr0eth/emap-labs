# emap/labs

`INFRAESTRUCTURA DE INTELIGENCIA GEOGRÁFICA · EUSKADI → EUROPA`

Laboratorio de datos e IA detrás de [emap](https://emap-next.vercel.app):
datasets urbanos versionados, búsqueda semántica, RAG geoespacial y
benchmarks de modelos en español y euskera. emap es el producto y el primer
consumidor de todo lo que sale de aquí.

**Estado: L0 en curso** — ver [docs/ROADMAP.md](docs/ROADMAP.md).

## Estructura

```
docs/       roadmap y decisiones
evals/      corpus dorados y (próximamente) harness de evaluación
datasets/   pipelines de datasets propios (barrios, zonas verdes, …)
```

## Relación con otros repos

| Repo | Papel |
|---|---|
| `../emap-next` | producto en producción; `packages/data-catalog` (manifest, quality, coverage) vive allí y labs lo consume como hermano |
| `../emapdev-stable` | legacy, solo lectura |

## Principios

- `DATOS ANTES QUE MODELOS` — no se entrena ni fine-tunea nada en este horizonte.
- `NO SE FINGE` — lo que no se puede medir se omite; los evals premian decir "no lo sé".
- `DOGFOODING` — nada cuenta como hecho hasta que emap lo usa en producción.
- `ES/EU EN PARIDAD` — el euskera se escribe, no se traduce.

Regla de decisión: cada desarrollo debe mejorar emap, ser reutilizable,
publicable como open source o vendible. Si no cumple ninguna, no se hace.
