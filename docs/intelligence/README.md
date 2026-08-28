# EMAP Intelligence

Documentación del corte técnico que convierte Labs en una pieza reutilizable
de EMAP Core sin crear un servicio nuevo ni duplicar el dominio de
`emap-next`.

- [`architecture.md`](architecture.md): límites, interfaces y flujo runtime.
- [`territories.md`](territories.md): contrato del pack territorial y estado.
- [`madrid-sources.md`](madrid-sources.md): shortlist oficial del primer pack
  Madrid y decisión por fuente.
- [`../../evals/README.md`](../../evals/README.md): retrieval, perfiles,
  métricas y política de held-out.
- [`../../mcp/README.md`](../../mcp/README.md): interfaz MCP.
- [`../ROADMAP.md`](../ROADMAP.md): roadmap general de Labs.

La evidencia de ejecución de este corte está en las pruebas de `tests/` y en
los comandos de verificación indicados en cada documento. No se atribuyen al
Core capacidades que todavía viven únicamente en routing o en clientes.
