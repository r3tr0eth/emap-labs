# EMAP Labs — Roadmap v0.3 · "de laboratorio a plataforma"

**Fecha:** 2026-07-08 (sustituye a v0.2 del 07-07 — historia en git) ·
**Equipo:** 1 persona + Claude Code · **Horizonte:** jul 2026 → mar 2027

EMAP Labs es la capa de datos e inteligencia detrás de emap. La v0.2 planificó
jul→jun; **la velocidad real ejecutó tres meses de plan en 48 horas**, así que
esta versión adelanta fechas, sube la ambición y añade una fase nueva (L5)
nacida del research: no existe infraestructura MCP de movilidad hiperlocal —
ese hueco es nuestro.

## Estado (2026-07-08)

| Fase | Estado |
|---|---|
| **L0 Fundación** | ✅ CERRADO — catálogo quality/coverage, dataset barrios, release v0.1 (7 datasets/12.732 registros) |
| **L1 Corte semántico** | ✅ CERRADO — harness (117 casos, held-out, CI con gates), híbrido en producción (`/api/semantic-search` + buscador), euskera validado con Itzuli |
| **L2 Knowledge layer** | 🟡 70% — explain-place descriptivo en prod (EN DESTINO), coverage_index + informe institucional, ética de datos escrita; falta texto generado (espera L3) |
| **D-018 (emap-next)** | ✅ OSRM propio + evitar autopistas real, señales labs en confort de ruta |

Hallazgo rector (curación Itzuli): con euskera correcto el semántico actual
EMPATA con keywords — **la brecha EU es real y mayor de lo medido**. Todo L3
existe para cerrarla con datos.

## Dónde vive / infra / principios

Sin cambios de v0.2: este repo (privado hasta L4) + `../emap-next` (producto);
VPS Hetzner propio (pendiente caja de 8 GB — CX33/CAX21 cuando haya stock,
Gaizka vigila manualmente); **OSS/EU-first innegociable en el producto**;
regla de oro financiera (~8-15 €/mes, emap solo gasta lo que trae);
`ETICA-DATOS.md` manda; held-out jamás calibra.

---

## Fases

### L3 — Benchmark y salto semántico (ADELANTADO: jul–sep 2026, era dic–ene)

La brecha EU medida convierte L3 en urgente. Tres carriles:

1. **Embeddings upgrade** (sin esperar servidor): sustituir MiniLM por
   **BGE-M3** (MIT, 100+ idiomas, denso+sparse en un modelo — el workhorse
   open de 2026) como clasificador de categoría; evaluar también
   Qwen3-Embedding (Apache-2). Se itera en dev, se decide en held-out.
   Jina descartado (CC-BY-NC — incompatible con uso comercial futuro).
2. **Clasificador LLM** (al llegar la caja de 8 GB): **Latxa 7B** cuantizado
   (HiTZ, el modelo DE euskera), Qwen3 pequeño y Mistral (API UE, única
   referencia comercial) como clasificadores de intención contra el corpus
   curado. Criterio: superar al híbrido en held-out EN AMBOS idiomas.
3. **Publicación** (sep, sincronizada con NLnet): "primer benchmark de
   retrieval geográfico en euskera" — metodología Itzuli-validada, corpus,
   resultados por modelo, coste/latencia. Contactar HiTZ al publicar (son
   aliados naturales: usamos Latxa y complementamos sus eval suites con un
   dominio que no cubren).

*Hecho cuando:* tabla pública de ≥4 modelos en ES/EU sobre el corpus, y el
mejor desplegado en producción tras batir al híbrido en held-out.

### L2-cierre — explain-place generativo (sep–oct, tras elegir modelo en L3)

Texto generado con citas de señales sobre el JSON de `/explain` (RAG de
verdad, modelo elegido POR el benchmark, no por vibes) + score de barrio
institucional integrado en el informe recurrente. pgvector entra aquí si
el volumen de documentos lo pide (hoy no).

### L4 — Abrir (ADELANTADO: oct–nov 2026, era feb–jun 2027)

1. **emap-datasets público** con cadencia trimestral (v0.2 en oct: + barrios,
   + tráfico completo, + scores) — primer OSS real de Labs.
2. **Piloto institucional**: el informe de cobertura como puerta de entrada
   (BEAZ/diputación); un piloto, no tres.
3. Solicitar **Claude for OSS** si dependientes/tracción lo permiten.
4. Kunoa como segundo consumidor de `packages/knowledge` si su calendario
   encaja (no bloquea).

### L5 — emap/agents: el MCP de movilidad hiperlocal (NUEVO — nov–dic 2026)

Research 2026-07-08: existen MCP genéricos de GTFS (uno, feed-a-feed) y de
OSM (varios), pero **nadie expone inteligencia de movilidad hiperlocal a
agentes**: búsqueda semántica local, explain-place, rutas con confort/señales
y tiempo real multi-red, bilingüe. Ese es exactamente nuestro stack.

1. **Servidor MCP open source** (`emap-mcp`) sobre los endpoints ya vivos:
   `/nearby`, `/semantic-search`, `/explain-place`, `/route` (+ RT). Corre
   en el VPS; herramientas con descripciones ES/EU/EN.
2. **llms.txt / docs agent-readable** del API público.
3. Distribución: registro MCP, awesome-lists, post técnico. Es
   simultáneamente producto (emap dentro de Claude/agentes de cualquiera),
   commons (perfil NLnet) y escaparate (BIND).

*Hecho cuando:* un agente externo (el Claude Desktop de cualquier usuario)
puede preguntar "¿dónde dejo la bici cerca de San Mamés?" y obtener la
respuesta de emap con atribución.

### Vertical mendi — montañismo/trail (ago–sep, ver VERTICAL-MENDI.md)

Ángulo propio frente a Wikiloc/Strava (no competimos en social/tracking):
**"el monte en transporte público"** — cimas y senderos homologados (1.130
cimas + 105 rutas en Bizkaia/OSM, GR-12 y senderos oficiales del catálogo)
cruzados con OTP: "qué cima hago el sábado en tren, con vuelta asegurada".
Dataset mendi → capa + cómo-llegar → casos de corpus → herramienta
`plan_hike` en emap-mcp (la demo agéntica estrella de L5).

### Transversales (goteo continuo)

- **Queries reales anonimizadas** (privacy-first, opt-out, sin PII) para
  sustituir el corpus sintético — el mayor multiplicador de calidad pendiente.
- **Crowdsourcing/auzolan** (ver CROWDSOURCING.md): v0 funnel a OSM (ya en
  prod) → v1 confirmaciones 👍/👎 con k-anonimato cuando haya usuarios →
  v2 campañas de accesibilidad OpenSidewalks con socio institucional.
  Capas de seguridad (DEA, montaña) inmunes al crowd.
- **Isócronas** ("qué alcanzo en 15 min") — key gratuita ORS o cálculo propio
  sobre OSRM/OTP.
- **Freshness**: cron determinista en el VPS para datos (GTFS/OSM/tráfico) +
  loop de agente solo para interpretar drift (convención CLAUDE.md).
- Releases trimestrales de datasets; informe de cobertura re-generado con
  cada release.

## Calendario de financiación (sin cambios, fechas verificadas)

Ago: borradores BIND (deadline **4-sep**) y NLnet → sep-oct: envíos →
invierno: entidad solo con dinero confirmado. Detalle en
`COSTES-Y-FINANCIACION.md`.

## No hacer (vigente)

Entrenar/fine-tunear modelos; expandir fuera de Euskadi antes de resolverlo;
depender de APIs US-cerradas en el producto; rankings de barrios en UI de
consumo; gastar sin ingreso confirmado; calibrar con held-out.

## Regla principal (vigente)

Cada desarrollo debe: mejorar emap, ser reutilizable, publicable como OSS o
vendible. Si no cumple ninguna, no se hace.
