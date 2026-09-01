# emap-mcp — movilidad hiperlocal de Euskadi para agentes

Servidor MCP (roadmap L5) sobre los endpoints públicos de
[emap](https://emapapp.com) / [API actual](https://emap-next.vercel.app).
No existe otro MCP de movilidad hiperlocal: búsqueda semántica local ES/EU,
contexto de lugar, rutas multimodales con infraestructura propia (OSRM/OTP)
y "el monte en transporte público".

**Versión:** 0.1.2 · wrapper de solo lectura · Apache-2.0

## Herramientas

| Tool | Qué hace |
|---|---|
| `search_places` | búsqueda semántica local en español o euskera, con abstención honesta |
| `nearby_pois` | POIs más cercanos por capa; resuelve el territorio por `territory` o coordenadas y siempre devuelve el contrato Core con evidencia y freshness |
| `explain_place` | barrio/municipio y servicios cercanos de un punto |
| `plan_route` | ruta real transit/walk/bike/car (OSRM/OTP propios) |
| `plan_hike` | cimas de Euskadi alcanzables en transporte público (2.825 × 9 redes) |

Toda respuesta incluye `attribution` (ODbL + GTFS oficiales + CC-BY-4.0).
Principio `NO SE FINGE`: si la API no sabe, la herramienta lo dice.

## Uso con Claude Desktop (stdio local)

```json
{
  "mcpServers": {
    "emap": {
      "command": "/ruta/a/emap-labs/.venv/bin/python",
      "args": ["/ruta/a/emap-labs/mcp/server.py"]
    }
  }
}
```

Requisitos: `python -m pip install mcp httpx` (o el venv del repo). El
servidor habla stdio y consume la API pública — no necesita credenciales.

## Modo HTTP (VPS, sin instalación local)

```bash
EMAP_MCP_TRANSPORT=streamable-http EMAP_MCP_PORT=8084 python mcp/server.py
```

`./mcp/deploy.sh` lo deja en el VPS (systemd `emap-mcp`, 127.0.0.1:8084).

| Superficie | URL | Estado |
|---|---|---|
| Endpoint objetivo | `https://vps.emapapp.com/mcp` | ✅ deploy 2026-08-30; initialize, tools/list y nearby contract verificados |
| Dominio de producto | `mcp.emapapp.com` o `emapapp.com/mcp` | ⏳ DNS/nginx (decisión abierta) |
| Health (local al proceso) | `GET http://127.0.0.1:8084/health` | ✅ desde 0.1.1 |

Cliente remoto (smoke verde):

```json
{"mcpServers": {"emap": {"url": "https://vps.emapapp.com/mcp"}}}
```

### Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `EMAP_MCP_TRANSPORT` | `stdio` | `streamable-http` en VPS |
| `EMAP_MCP_HOST` / `PORT` | `127.0.0.1` / `8084` | bind del proceso |
| `EMAP_MCP_ALLOWED_HOSTS` | local + gaizkajimenez + emapapp* | Hosts permitidos (anti rebinding; incluye el dominio anterior durante la transición) |
| `EMAP_API_URL` | `https://emap-next.vercel.app` | API que envuelve el MCP |
| `EMAP_SEMANTIC_URL` | `https://vps.emapapp.com/semantic` | Servicio Labs para planificación de montaña |
| `EMAP_SITE_URL` | `https://emapapp.com` | marca en atribución / website |

Snippet nginx (path o subdominio): `nginx.example.conf`.

## Verificación

- **2026-07-10** — cliente MCP stdio real → `nearby_pois(bikepark, San Mamés)`
  → aparcabicis a 47 m con atribución (criterio L5.1). Las 5 herramientas
  probadas contra producción.
- **Post-deploy** — `deploy.sh` hace `GET /health` + `initialize` JSON-RPC
  en localhost:8084.
- **Smoke automatizado** (`mcp/smoke.py`):

```bash
# local (servidor en :8084)
EMAP_MCP_TRANSPORT=streamable-http .venv/bin/python mcp/server.py &
.venv/bin/python mcp/smoke.py --base http://127.0.0.1:8084

# endpoint objetivo
.venv/bin/python mcp/smoke.py --base https://vps.emapapp.com --live

# cuando exista el dominio de producto
.venv/bin/python mcp/smoke.py --base https://mcp.emapapp.com --live
```

### Rollback

`mcp/deploy.sh` actualiza solo `/opt/emap-labs/mcp/server.py` y la unidad
systemd. Antes de desplegar, conservar la copia anterior del fichero y de
`/etc/systemd/system/emap-mcp.service`; si falla `health` o `initialize`,
restaurarlas, ejecutar `systemctl daemon-reload && systemctl restart emap-mcp`
y repetir el smoke. El rollback no toca datos ni el servicio semántico.

## Distribución (L5.3)

- **Registro oficial MCP**: `io.github.r3tr0eth/emap`
  (registry.modelcontextprotocol.io, remote streamable-http, status
  active — 2026-07-10). `server.json` en este directorio.
- `server.json` apunta a `vps.emapapp.com/mcp`; el redeploy y smoke público ya
  están verificados. El dominio anterior continúa en la allowlist durante la
  transición.
- `llms.txt` del API: https://emap-next.vercel.app/llms.txt
- Pendiente: PR a awesome-mcp-servers y post técnico (borradores listos);
  migrar URL pública a dominio `emapapp.com`.
