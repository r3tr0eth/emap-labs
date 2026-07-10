#!/usr/bin/env bash
# Despliegue de emap-mcp (modo streamable-http) al VPS (idempotente).
# Uso: ./mcp/deploy.sh [host]   (default root@gaizkajimenez.com)
#
# Deja el servidor en 127.0.0.1:8084 tras systemd (emap-mcp.service).
# El location /mcp de nginx se añade UNA vez a mano (ver README): proxy
# a 8084 con buffering off (streamable-http es de larga duración).
set -euo pipefail
HOST="${1:-root@gaizkajimenez.com}"
LABS="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ código"
ssh "$HOST" "mkdir -p /opt/emap-labs/mcp"
rsync -az "$LABS/mcp/server.py" "$HOST:/opt/emap-labs/mcp/"

echo "→ dependencias (reutiliza el venv del servicio semántico)"
ssh "$HOST" '/opt/emap-labs/.venv/bin/pip install -q mcp httpx'

echo "→ systemd"
ssh "$HOST" 'cat > /etc/systemd/system/emap-mcp.service <<UNIT
[Unit]
Description=emap-mcp (movilidad hiperlocal para agentes, streamable-http)
After=network.target

[Service]
User=emap
WorkingDirectory=/opt/emap-labs/mcp
Environment=EMAP_MCP_TRANSPORT=streamable-http
Environment=EMAP_MCP_HOST=127.0.0.1
Environment=EMAP_MCP_PORT=8084
ExecStart=/opt/emap-labs/.venv/bin/python /opt/emap-labs/mcp/server.py
Restart=on-failure
MemoryHigh=200M
MemoryMax=300M

[Install]
WantedBy=multi-user.target
UNIT
chown -R emap:emap /opt/emap-labs/mcp
systemctl daemon-reload && systemctl enable --now emap-mcp && systemctl restart emap-mcp'

echo "→ hecho. Verificar en el VPS: curl -s -X POST localhost:8084/mcp \\"
echo "   -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \\"
echo "   -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-03-26\",\"capabilities\":{},\"clientInfo\":{\"name\":\"curl\",\"version\":\"0\"}}}'"
