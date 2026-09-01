# EMAP Intelligence/Core — release gate v0.3

Estado del corte: **v0.3.0-rc.1** (sin tag aún; los tags llegan a v0.2.1).
Este documento no autoriza un deploy ni promueve la release a estable; reúne
evidencia y pendientes. Última revisión: 2026-08-31.

## Gates

| Gate | Estado | Evidencia / pendiente |
|---|---|---|
| Euskadi + Madrid en una instancia lógica | ✅ | `RuntimeRegistry`, `/healthz`, verificado en prod (search/nearby/404 por territorio, 2026-08-31) |
| 3 dominios Madrid | ✅ | `fountains`, `parking`, `bikepark`; 9.767 POIs |
| Madrid development | ✅ | 60 casos, corpus 0.2.0: baseline 46/60, hybrid MiniLM 53/60 (2026-08-31) y hybrid E5 Large 53/60 (2026-09-01); semantic MiniLM 46/60 (2026-08-30) |
| Gate E5 Large Madrid | ✅ | primera medición REAL del perfil 0.8/0.01 (2026-09-01, VPS, tras arreglar el bug del harness que ejecutaba MiniLM etiquetado como e5large): Madrid 53/60 (88%) → gate 85; Euskadi 70/82 ES (85%) y 68/82 EU (82%) → gates subidos a 80/78, por encima del rendimiento MiniLM para que una regresión de modelo ponga el gate en rojo; pendiente de correr en GitHub |
| Madrid held-out sellado | ✅ | 19 casos; `evals/madrid-heldout-seal.json` (sha256 verificado contra el corpus); job manual `run_heldout_madrid`, medición única |
| Response Contract v1 | ✅ | `/search` y `/nearby`, `intelligence.response.v1`; `validate_response()` en cada build; errores con `schema_version` |
| Answer status / abstention | ✅ | 4 estados con tests (incl. ABSTAINED); `STALE_EVIDENCE` como limitación en respuestas con evidencia stale; calibración estadística posterior |
| Evidence + freshness | ✅ | fuente, URL, licencia, actualización, ingesta y SLA por territorio con fallback neutro (sin fuga entre territorios) |
| Confidence v1 | ✅ parcial | señales deterministas; no es probabilidad calibrada; el score no agrega los factores (pendiente) |
| MCP local | ✅ | health, initialize y `tools/list` (5 tools); `search_places` propaga el contrato completo incl. `took_ms` |
| MCP remoto | ✅ | deploy systemd en VPS + smoke público `SMOKE OK`; `/health` raíz no se expone por nginx (pendiente); las mejoras de contrato de esta revisión requieren redeploy |
| Telemetría mínima | ✅ local | `/metrics` sin texto ni coordenadas; `no_result`/`abstained`/`unsupported` separados; `source_failure` con disparador real; persistencia futura |
| Demo nearby verificable | ✅ | Labs → API → MCP; evidencia por entidad |
| Integración visible mapa | ✅ | marca `Fuente verificada` con freshness fresh |
| CI completa | ⏳ | job `suite Labs` (`pytest tests -q`, 46 tests, deps pinneadas, skip de MCP prohibido con `CI=1`, checkout del hermano emap-next); verde en local y en simulación del runner; pendiente: crear el secret `EMAP_NEXT_DEPLOY_KEY` (deploy key de solo lectura sobre emap-next) y ver la primera ejecución verde en GitHub |
| Documentación | ✅ | docs de intelligence al día con el corte 2026-08-31; CHANGELOG/RELEASE-NOTES de la RC actualizados |
| Code-review final | ⏳ | `/code-review` antes de mergear a main (regla del workspace) |

## Criterio de promoción

La release permanece candidate mientras la suite completa de Labs y el gate del
perfil E5 Large de producción no tengan evidencia reproducible en GitHub, y
mientras no pase la code-review final. No se afirma cobertura completa de
Madrid, generalización europea ni TRL 5.
