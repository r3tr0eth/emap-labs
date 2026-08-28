#!/usr/bin/env bash
# Despliegue de emap-mcp (modo streamable-http) al VPS (idempotente).
# Uso: ./mcp/deploy.sh [host]   (default root@vps.emapapp.com)
#
# Deja el servidor en 127.0.0.1:8084 tras systemd (emap-mcp.service).
# Nginx se configura a mano una vez (ver mcp/nginx.example.conf):
#   - prod actual:  https://vps.emapapp.com/mcp
#   - transición:   host allowlist ya incluye emapapp.com y mcp.emapapp.com
#   - cuando haya DNS/TLS del dominio de producto, solo nginx + registry.
set -euo pipefail
HOST="${1:-root@vps.emapapp.com}"
LABS="$(cd "$(dirname "$0")/.." && pwd)"

# Hosts públicos aceptados por la protección anti DNS-rebinding del SDK.
# Incluye dominio personal (prod hoy) + candidatos del dominio de producto
# mientras se decide path (emapapp.com/mcp) vs subdominio (mcp.emapapp.com).
ALLOWED_HOSTS="${EMAP_MCP_ALLOWED_HOSTS:-127.0.0.1:8084,localhost:8084,vps.emapapp.com,emapapp.com,mcp.emapapp.com,www.emapapp.com}"
API_URL="${EMAP_API_URL:-https://emap-next.vercel.app}"
SEMANTIC_URL="${EMAP_SEMANTIC_URL:-https://vps.emapapp.com/semantic}"
SITE_URL="${EMAP_SITE_URL:-https://emapapp.com}"

echo "→ código"
ssh "$HOST" "mkdir -p /opt/emap-labs/mcp"
rsync -az "$LABS/mcp/server.py" "$HOST:/opt/emap-labs/mcp/"

echo "→ dependencias (reutiliza el venv del servicio semántico)"
ssh "$HOST" '/opt/emap-labs/.venv/bin/pip install -q "mcp>=1.0" httpx'

echo "→ systemd"
ssh "$HOST" "cat > /etc/systemd/system/emap-mcp.service <<UNIT
[Unit]
Description=emap-mcp (movilidad hiperlocal para agentes, streamable-http)
After=network.target

[Service]
User=emap
WorkingDirectory=/opt/emap-labs/mcp
Environment=EMAP_MCP_TRANSPORT=streamable-http
Environment=EMAP_MCP_HOST=127.0.0.1
Environment=EMAP_MCP_PORT=8084
Environment=EMAP_MCP_ALLOWED_HOSTS=${ALLOWED_HOSTS}
Environment=EMAP_API_URL=${API_URL}
Environment=EMAP_SEMANTIC_URL=${SEMANTIC_URL}
Environment=EMAP_SITE_URL=${SITE_URL}
ExecStart=/opt/emap-labs/.venv/bin/python /opt/emap-labs/mcp/server.py
Restart=on-failure
MemoryHigh=200M
MemoryMax=300M

[Install]
WantedBy=multi-user.target
UNIT
chown -R emap:emap /opt/emap-labs/mcp
systemctl daemon-reload && systemctl enable --now emap-mcp && systemctl restart emap-mcp"

echo "→ verificación post-deploy (health + initialize)"
ssh "$HOST" 'sleep 1
set -e
curl -sf http://127.0.0.1:8084/health | head -c 400
echo
curl -s -o /tmp/emap-mcp-init.json -w "initialize_http=%{http_code}\n" -X POST http://127.0.0.1:8084/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-03-26\",\"capabilities\":{},\"clientInfo\":{\"name\":\"deploy\",\"version\":\"0\"}}}"
head -c 300 /tmp/emap-mcp-init.json; echo'

echo "→ hecho. Público actual: https://vps.emapapp.com/mcp"
echo "   Producto (pendiente DNS/nginx): mcp.emapapp.com o emapapp.com/mcp"
echo "   Snippet nginx: mcp/nginx.example.conf"
echo "   Smoke desde el portátil:"
echo "     .venv/bin/python mcp/smoke.py --base https://vps.emapapp.com --live"
