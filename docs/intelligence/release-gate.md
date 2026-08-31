# EMAP Intelligence/Core — release gate v0.3

Estado del corte: **v0.3.0-rc.1**. Este documento no autoriza un deploy ni
promueve la release a estable; reúne evidencia y pendientes.

## Gates

| Gate | Estado | Evidencia / pendiente |
|---|---|---|
| Euskadi + Madrid en una instancia lógica | ✅ | `RuntimeRegistry`, `/healthz`, smoke con datos reales |
| 3 dominios Madrid | ✅ | `fountains`, `parking`, `bikepark`; 9.767 POIs |
| Madrid development | ✅ parcial | 60 casos; baseline 46/60, semantic 46/60, hybrid MiniLM 53/60; falta gate E5 Large de producción |
| Madrid held-out sellado | ✅ | 19 casos; `evals/madrid-heldout-seal.json` |
| Response Contract v1 | ✅ | `/search` y `/nearby`, `intelligence.response.v1` |
| Answer status / abstention | ✅ parcial | estados explícitos; calibración estadística posterior |
| Evidence + freshness | ✅ | fuente, URL, licencia, actualización, ingesta y SLA |
| Confidence v1 | ✅ parcial | señales deterministas; no es probabilidad calibrada |
| MCP local | ✅ | health, initialize y `tools/list` (5 tools) |
| MCP remoto | ✅ | deploy systemd en VPS + smoke público `SMOKE OK`; `/health` raíz no se expone por nginx |
| Telemetría mínima | ✅ local | `/metrics`, sin texto ni coordenadas; persistencia futura |
| Demo nearby verificable | ✅ | Labs → API → MCP; evidencia por entidad |
| Integración visible mapa | ✅ | marca `Fuente verificada` con freshness fresh |
| CI completa | ⏳ | job `suite Labs (contratos y servicio)` añadido para `pytest tests -q`; pendiente de su primera ejecución en GitHub |

## Criterio de promoción

La release permanece candidate mientras la suite completa de Labs y el gate del
perfil E5 Large de producción no tengan evidencia reproducible. No se afirma cobertura completa de Madrid,
generalización europea ni TRL 5.
