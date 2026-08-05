#!/usr/bin/env bash
# Despliegue del servicio semántico al VPS (idempotente).
# Uso: ./service/deploy.sh [host]   (default root@gaizkajimenez.com)
set -euo pipefail
HOST="${1:-root@gaizkajimenez.com}"
LABS="$(cd "$(dirname "$0")/.." && pwd)"
NEXT="$LABS/../emap-next"

echo "→ código y datos"
ssh "$HOST" "mkdir -p /opt/emap-labs/{service,evals,data/pois-euskadi,data/processed/pois,data/processed/neighborhoods}"
rsync -az "$LABS/service/app.py" "$HOST:/opt/emap-labs/service/"
rsync -az "$LABS/evals/baseline.py" "$LABS/evals/semantic_local.py" "$HOST:/opt/emap-labs/evals/"
rsync -az "$NEXT/packages/geo" "$HOST:/opt/emap-labs/" --exclude __pycache__ --exclude '*.egg-info'
rsync -az "$NEXT/data/pois-euskadi/" "$HOST:/opt/emap-labs/data/pois-euskadi/"
rsync -az "$NEXT/data/pois-euskadi/peaks.json" "$HOST:/opt/emap-labs/data/pois-euskadi/"
rsync -az "$NEXT/data/processed/pois/" "$HOST:/opt/emap-labs/data/processed/pois/"
rsync -az "$NEXT/data/processed/neighborhoods/neighborhoods.json" "$HOST:/opt/emap-labs/data/processed/neighborhoods/"

echo "→ venv + dependencias"
ssh "$HOST" 'cd /opt/emap-labs && [ -d .venv ] || python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q fastembed fastapi "uvicorn[standard]" numpy scipy ./geo
  # fastembed con soporte de rerank (ONNX). Misma versión, reclama el extra.
  # Si ya estaba instalado sin rerank, esto lo amplía.'

echo "→ systemd"
ssh "$HOST" 'cat > /etc/systemd/system/emap-semantic.service <<UNIT
[Unit]
Description=emap-labs semantic search (hybrid retriever)
After=network.target

[Service]
User=emap
WorkingDirectory=/opt/emap-labs/service
Environment=EMAP_DATA_DIR=/opt/emap-labs/data
Environment=HF_HOME=/opt/emap-labs/.cache
# e5-large (L3, 2026-08-05): modelo ganador del benchmark (75/81% held-out
# ES/EU). Calibración propia para 21 capas (2026-07-09): τ 0.80, tie 0.01.
Environment=EMAP_EMBED_MODEL=intfloat/multilingual-e5-large
Environment=EMAP_SIM_TAU=0.80
Environment=EMAP_TIE_WIN=0.01
ExecStart=/opt/emap-labs/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8083
Restart=on-failure
MemoryHigh=3G
MemoryMax=4G

[Install]
WantedBy=multi-user.target
UNIT
mkdir -p /opt/emap-labs/.cache && chown -R emap:emap /opt/emap-labs
systemctl daemon-reload && systemctl enable --now emap-semantic'

echo "→ reinicio"
ssh "$HOST" "systemctl restart emap-semantic"

echo "→ verificación post-deploy"
# Espera activa a que el servicio arranque (máx 30s), luego verifica
# healthz Y una query real. Un deploy "exitoso" con el servicio muerto
# no cuenta como éxito.
for i in $(seq 1 30); do
  if ssh "$HOST" "curl -fs localhost:8083/healthz" 2>/dev/null | grep -q '"ok":true'; then
    break
  fi
  sleep 1
done
if ! ssh "$HOST" "curl -fs localhost:8083/healthz" 2>/dev/null | grep -q '"ok":true'; then
  echo "ERROR: el servicio no arrancó correctamente tras 30s" >&2
  ssh "$HOST" "journalctl -u emap-semantic --no-pager -n 30" >&2
  exit 1
fi
# Query real: verifica que el retriever funciona, no solo que uvicorn escucha
RESULT="$(ssh "$HOST" "curl -fs 'localhost:8083/search?q=fuente&lat=43.263&lon=-2.935'")"
if echo "$RESULT" | grep -q '"results"'; then
  echo "→ deploy OK: healthz verde + búsqueda funcional"
else
  echo "ERROR: el servicio responde pero la búsqueda no devuelve resultados" >&2
  echo "$RESULT" >&2
  exit 1
fi
