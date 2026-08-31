# EMAP Intelligence

Documentación del corte técnico que convierte Labs en una pieza reutilizable
de EMAP Core sin crear un servicio nuevo ni duplicar el dominio de
`emap-next`.

- [`architecture.md`](architecture.md): límites, interfaces y flujo runtime.
- [`territories.md`](territories.md): contrato del pack territorial y estado.
- [`madrid-sources.md`](madrid-sources.md): shortlist oficial del primer pack
  Madrid y decisión por fuente.
- [`response-contract.md`](response-contract.md): contrato versionado de
  respuesta, evidencia, freshness y confidence.
- [`telemetry.md`](telemetry.md): métricas agregadas privacy-first del servicio.
- [`release-gate.md`](release-gate.md): estado verificable de promoción de la
  release candidate.
- [`cross-territory.md`](cross-territory.md): comparación medida y sus límites
  estadísticos.
- La demo verificable está disponible en `GET /nearby` y en
  `GET /api/intelligence/nearby`; MCP la expone mediante `nearby_pois` cuando
  se proporciona `territory`.
- [`../../evals/README.md`](../../evals/README.md): retrieval, perfiles,
  métricas y política de held-out.
- [`../../mcp/README.md`](../../mcp/README.md): interfaz MCP.
- [`../ROADMAP.md`](../ROADMAP.md): roadmap general de Labs.

La evidencia de ejecución de este corte está en las pruebas de `tests/` y en
los comandos de verificación indicados en cada documento. No se atribuyen al
Core capacidades que todavía viven únicamente en routing o en clientes.
