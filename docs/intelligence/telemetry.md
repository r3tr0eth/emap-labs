# Telemetría Intelligence

`service/app.py` mantiene contadores agregados por proceso y expone `GET
/metrics`. Registra requests, territorio, retriever/perfil, latencia,
resultados, abstenciones, unsupported, errores de entrada/servicio y fuentes stale. No guarda texto de consulta ni coordenadas; el
log opcional conserva únicamente un hash corto de la query para correlación
operativa. Es una primera capa, no un sistema distribuido de observabilidad.

El reinicio del proceso reinicia los contadores. La persistencia y alertas se
dejan para una iteración posterior cuando exista una necesidad operativa real.
