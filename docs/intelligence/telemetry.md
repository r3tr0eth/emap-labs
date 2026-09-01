# Telemetría Intelligence

`service/app.py` mantiene contadores agregados por proceso y expone `GET
/metrics`. Registra requests, territorio, retriever/perfil, latencia (total y
media), y por `answer_status` del contrato: `no_result` (corpus sin match),
`abstained` (detección bajo umbral) y `unsupported` (categoría no soportada)
son señales distintas. `stale_source` cuenta resultados servidos con evidencia
stale; `source_failure` cuenta resultados servidos sin documento de fuente
(metadatos ausentes); `errors` cuenta fallos de entrada/servicio (rate-limit,
runtime sin inicializar, territorio inválido, capa no soportada).

Solo `/search` y `/nearby` instrumentan el camino de éxito; los endpoints
experimentales (tts, hike, accessible, isochrone) y las tools MCP no
registran telemetría todavía. `success` significa "petición atendida", no
éxito semántico.

No guarda texto de consulta ni coordenadas; el log diario de queries (ruta
configurable con `EMAP_QUERY_LOG`; siempre activo, sus fallos se silencian)
conserva únicamente un hash corto de la query para correlación operativa. Es una
primera capa, no un sistema distribuido de observabilidad.

El reinicio del proceso reinicia los contadores. La persistencia, la
distribución de latencias (percentiles) y las alertas se dejan para una
iteración posterior cuando exista una necesidad operativa real.
