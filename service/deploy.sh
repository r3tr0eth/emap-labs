#!/usr/bin/env bash
# Despliegue del servicio semántico al VPS (idempotente).
# Uso: ./service/deploy.sh [host]   (default root@gaizkajimenez.com)
set -euo pipefail
HOST="${1:-root@gaizkajimenez.com}"
LABS="$(cd "$(dirname "$0")/.." && pwd)"
NEXT="$LABS/../emap-next"

echo "→ código y datos"
ssh "$HOST" "mkdir -p /opt/emap-labs/{service,evals,data/pois-euskadi,data/processed/pois}"
rsync -az "$LABS/service/app.py" "$HOST:/opt/emap-labs/service/"
rsync -az "$LABS/evals/baseline.py" "$LABS/evals/semantic_local.py" "$HOST:/opt/emap-labs/evals/"
rsync -az "$NEXT/packages/geo" "$HOST:/opt/emap-labs/" --exclude __pycache__ --exclude '*.egg-info'
rsync -az "$NEXT/data/pois-euskadi/" "$HOST:/opt/emap-labs/data/pois-euskadi/"
rsync -az "$NEXT/data/processed/pois/" "$HOST:/opt/emap-labs/data/processed/pois/"

echo "→ venv + dependencias"
ssh "$HOST" 'cd /opt/emap-labs && [ -d .venv ] || python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q fastembed fastapi "uvicorn[standard]" numpy ./geo'

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
ExecStart=/opt/emap-labs/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8083
Restart=on-failure
MemoryHigh=700M
MemoryMax=1G

[Install]
WantedBy=multi-user.target
UNIT
mkdir -p /opt/emap-labs/.cache && chown -R emap:emap /opt/emap-labs
systemctl daemon-reload && systemctl enable --now emap-semantic'

echo "→ hecho. Verificar: curl -s localhost:8083/healthz (en el VPS)"
