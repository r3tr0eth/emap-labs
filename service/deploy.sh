#!/usr/bin/env bash
# Despliegue del servicio semántico al VPS (idempotente).
# Uso: ./service/deploy.sh [host]   (default root@vps.emapapp.com)
set -euo pipefail
HOST="${1:-root@vps.emapapp.com}"
LABS="$(cd "$(dirname "$0")/.." && pwd)"
NEXT="$LABS/../emap-next"

echo "→ código y datos"
ssh "$HOST" "mkdir -p /opt/emap-labs/{service,evals,regions/euskadi,regions/madrid,data/pois-euskadi,data/processed/pois,data/processed/madrid/pois,data/processed/neighborhoods}"
# NOTA: añadir aquí cualquier nuevo módulo *.py de service/
rsync -az "$LABS/service/app.py" "$LABS/service/runtime.py" "$LABS/service/response_contract.py" "$LABS/service/explain.py" "$LABS/service/hike_planner.py" "$LABS/service/accessibility.py" "$LABS/service/isochrones.py" "$LABS/service/data_freshness.py" "$LABS/service/tts.py" "$HOST:/opt/emap-labs/service/"
rsync -az "$LABS/evals/baseline.py" "$LABS/evals/semantic_local.py" "$LABS/evals/retriever_config.py" "$LABS/evals/retriever-config.json" "$LABS/evals/requirements.txt" "$HOST:/opt/emap-labs/evals/"
rsync -az "$LABS/regions/__init__.py" "$LABS/regions/registry.py" "$HOST:/opt/emap-labs/regions/"
rsync -az "$LABS/regions/euskadi/region.yaml" "$HOST:/opt/emap-labs/regions/euskadi/"
rsync -az "$LABS/regions/madrid/region.yaml" "$HOST:/opt/emap-labs/regions/madrid/"
rsync -az "$NEXT/packages/geo" "$HOST:/opt/emap-labs/" --exclude __pycache__ --exclude '*.egg-info'
rsync -az "$NEXT/data/pois-euskadi/" "$HOST:/opt/emap-labs/data/pois-euskadi/"
rsync -az "$NEXT/data/pois-euskadi/peaks.json" "$HOST:/opt/emap-labs/data/pois-euskadi/"
rsync -az "$NEXT/data/processed/pois/" "$HOST:/opt/emap-labs/data/processed/pois/"
rsync -az "$NEXT/data/processed/madrid/pois/" "$HOST:/opt/emap-labs/data/processed/madrid/pois/"
rsync -az "$NEXT/data/processed/neighborhoods/neighborhoods.json" "$HOST:/opt/emap-labs/data/processed/neighborhoods/"

echo "→ venv + dependencias"
ssh "$HOST" 'cd /opt/emap-labs && [ -d .venv ] || python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r evals/requirements.txt fastapi "uvicorn[standard]" scipy ./geo
  # TTS euskera (Piper Maider). Falla en silencio si no hay espeak-ng;
  # fetch-maider.sh + apt install espeak-ng son el paso humano.
  ./.venv/bin/pip install -q piper-tts || true'

echo "→ systemd"
ssh "$HOST" 'cat > /etc/systemd/system/emap-semantic.service <<UNIT
[Unit]
Description=emap-labs semantic search (hybrid retriever)
After=network.target

[Service]
User=emap
WorkingDirectory=/opt/emap-labs/service
Environment=EMAP_DATA_DIR=/opt/emap-labs/data
Environment=EMAP_TERRITORIES=euskadi,madrid
Environment=EMAP_PIPER_DIR=/opt/emap-labs/tts
Environment=HF_HOME=/opt/emap-labs/.cache
# El perfil versionado une modelo y calibración; evita deriva CI/prod.
Environment=EMAP_RETRIEVER_PROFILE=e5large
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
EUSKADI_RESULT="$(ssh "$HOST" "curl -fs 'localhost:8083/search?q=fuente&territory=euskadi&lat=43.263&lon=-2.935'")"
MADRID_RESULT="$(ssh "$HOST" "curl -fs 'localhost:8083/search?q=fuente&territory=madrid&lat=40.4168&lon=-3.7038'")"
MADRID_NEARBY="$(ssh "$HOST" "curl -fs 'localhost:8083/nearby?layer=parking&territory=madrid&lat=40.4168&lon=-3.7038&k=1'")"
if echo "$EUSKADI_RESULT" | grep -q '"territory":"euskadi"' \
  && echo "$MADRID_RESULT" | grep -q '"territory":"madrid"' \
  && echo "$MADRID_NEARBY" | grep -q '"schema_version":"intelligence.response.v1"'; then
  echo "→ deploy OK: healthz verde + Euskadi/Madrid + nearby contract"
else
  echo "ERROR: el servicio no preserva ambos territorios" >&2
  echo "$EUSKADI_RESULT" >&2
  echo "$MADRID_RESULT" >&2
  echo "$MADRID_NEARBY" >&2
  exit 1
fi
