# emap-mcp — movilidad hiperlocal de Euskadi para agentes

Servidor MCP (roadmap L5) sobre los endpoints públicos de
[emap](https://emap-next.vercel.app). No existe otro MCP de movilidad
hiperlocal: búsqueda semántica local ES/EU, contexto de lugar, rutas
multimodales con infraestructura propia (OSRM/OTP) y "el monte en
transporte público".

## Herramientas

| Tool | Qué hace |
|---|---|
| `search_places` | búsqueda semántica local en español o euskera, con abstención honesta |
| `nearby_pois` | POIs más cercanos por capa (fuentes, aseos, DEA, cimas, paradas…) |
| `explain_place` | barrio/municipio y servicios cercanos de un punto |
| `plan_route` | ruta real transit/walk/bike/car (OSRM/OTP propios) |
| `plan_hike` | cimas de Euskadi alcanzables en transporte público (2.825 × 9 redes) |

Toda respuesta incluye `attribution` (ODbL + GTFS oficiales + CC-BY-4.0).
Principio `NO SE FINGE`: si la API no sabe, la herramienta lo dice.

## Uso con Claude Desktop

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

## Verificación (2026-07-10)

Cliente MCP stdio real → `nearby_pois(bikepark, San Mamés)` → aparcabicis a
47 m con atribución: el criterio de "hecho" de L5.1 del roadmap. Las 5
herramientas probadas contra producción (plan_hike: Arraiz 345 m con parada
a 562 m; plan_route: bus A5 con transbordos y tiempos).

## Modo HTTP (VPS, sin instalación local)

El servidor también habla `streamable-http`:

```bash
EMAP_MCP_TRANSPORT=streamable-http EMAP_MCP_PORT=8084 python mcp/server.py
```

`./mcp/deploy.sh` lo deja en el VPS (systemd `emap-mcp`, 127.0.0.1:8084)
tras nginx en `https://gaizkajimenez.com/mcp` — config de cliente remoto:

```json
{"mcpServers": {"emap": {"url": "https://gaizkajimenez.com/mcp"}}}
```

## Distribución (L5.3)

- **Registro oficial MCP**: publicado como `io.github.r3tr0eth/emap`
  (registry.modelcontextprotocol.io, remote streamable-http, status
  active — 2026-07-10). `server.json` en este directorio.
- `llms.txt` del API: https://emap-next.vercel.app/llms.txt
- Pendiente: PR a awesome-mcp-servers y post técnico (borradores listos).
