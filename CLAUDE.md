# CLAUDE.md — emap-labs

Capa de datos e inteligencia detrás de emap (github.com/r3tr0eth/emap-labs,
público). Roadmap: `docs/ROADMAP.md`. Reglas duras: `docs/ETICA-DATOS.md`
(infraestructura jamás personas) y la regla financiera: emap solo gasta
dinero que emap trae.

## Relación con otros repos

- `../emap-next`: producto en producción (Vercel + VPS Hetzner). **Sin remoto
  git** — solo commits locales; deploy con `vercel deploy --prod --yes`.
- Los pipelines de `datasets/` escriben en `emap-next/data/processed/` y se
  registran en su manifest (`python -m data_catalog validate|quality|check`
  con el venv de emap-next).

## Comandos

```bash
../emap-next/.venv/bin/python evals/run.py [--retriever baseline|semantic|hybrid] \
    [--lang es|eu] [--split dev|heldout|all] [--min-pass N]   # evals
./evals/sync-data.sh              # refrescar snapshot para CI tras cambiar datos
../emap-next/.venv/bin/python datasets/<pipeline>/build.py    # pipelines
./service/deploy.sh               # desplegar servicio semántico al VPS
ssh root@gaizkajimenez.com        # VPS (OTP :8082, semantic :8083, nginx)
```

- Venv propio (`.venv`, python3.13: fastembed/numpy) solo para el retriever
  semántico; todo lo demás usa el venv de emap-next.
- **held-out (`ho-*`) jamás se usa para calibrar**; si se mira para depurar,
  se promociona a dev y se escriben casos nuevos.
- CI corre en cada push (`.github/workflows/evals.yml`) con gates --min-pass;
  si tocas retriever o corpus, actualiza los umbrales conscientemente en el
  mismo PR, nunca para "que pase".

## Loops (convención de trabajo con Claude Code)

Regla previa: **lo determinista va en scripts** (cron del VPS o `*.sh` del
repo), los bucles de agente son para juicio e iteración. Recetas:

- **Turn-based + verificación**: cualquier cambio de retriever/corpus termina
  con `evals/run.py` en dev (ES y EU) antes de commitear; cambios de UI en
  emap-next, con la skill `verify-frontend-change` / QA CDP.
- **`/goal` con gate de eval** (el mejor encaje: criterio determinista):
  `/goal sube hybrid held-out EU a ≥75% sin bajar ES de 79% ni dev, máx 5
  intentos` — tocando solo dev para iterar; held-out se corre UNA vez al final.
- **`/loop` para CI**: tras push con cambios de evals,
  `/loop 5m mira el workflow evals de emap-labs y arregla si falla`.
- **Proactivo (pendiente de activar, consume cuota — decidir Gaizka)**:
  rutina semanal sobre este repo: re-ejecutar pipelines con fetch remoto
  (neighborhoods/Overpass), `sync-data.sh`, evals completas, y abrir issue
  si hay drift de datos o caída de gates. Solo tiene sentido semanal —
  las fuentes no cambian más rápido.

## Convenciones

- Commits convencionales en español (`feat(evals): …`, scopes: evals,
  datasets, service, mcp, docs, ci). No commitear sin que Gaizka lo pida.
- Datos: cada dataset con los 6 metadatos; `coverage.completeness` solo si es
  estimable honestamente; sesgo de mapeo OSM declarado en `coverage.notes`.
- No se finge: abstención antes que inventar, en retrievers y en prosa.
