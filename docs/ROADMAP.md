# EMAP Labs — Roadmap realista v0.2

**Fecha:** 2026-07-07 · **Equipo:** 1 persona + Claude Code · **Horizonte:** jul 2026 → jun 2027

EMAP Labs es la capa de datos e inteligencia detrás de EMAP: **en gran parte
formaliza trabajo que ya existe en `../emap-next`** y le añade lo que falta
(capa semántica, evals, datasets propios). Este documento sustituye al borrador
fundacional (ChatGPT, jul 2026) con un plan anclado en lo que hay construido y
en lo que una persona puede ejecutar de verdad.

---

## Punto de partida — lo que Labs ya tiene sin llamarse Labs

| Objetivo del borrador | Estado real en emap-next |
|---|---|
| Pipeline de datasets con metadatos | ✅ 70% — `packages/data-catalog` (manifest de 37 datasets, checksums, CLI validate/refresh), `sources.yml` con licencia/fuente/fecha. Falta: `quality` y `coverage` como campos formales, y versionado de releases |
| Knowledge layer semántica | ✅ embrión — modelo `UrbanSignal` (14 tipos de señal vivos: incidencias, alertas RT, arbolado, iluminación, pendiente, retenciones históricas…) documentado en `URBAN-SIGNALS.md` |
| Datasets iniciales (lugares/transporte/zonas verdes/accesibilidad) | ✅ lugares (9.138 POIs + DEA + aparcabicis), ✅ transporte (5 redes GTFS+RT), 🟡 zonas verdes (arbolado por corredor, falta capa completa), 🟡 accesibilidad (wheelchair OTP; esquema OpenSidewalks adoptado, sin datos). ❌ **barrios — el único que falta entero** |
| Sistema de evaluación | ✅ metodología probada — golden data (52/52 live, benchmark 25 rutas, 1.800 casos del recomendador). Falta aplicarla a preguntas semánticas |
| APIs reutilizables | ✅ 16 endpoints en producción; `recommend` dentro de `/api/route`. Faltan `/nearby` semántico y `/semantic-search` |
| RAG (pgvector + embeddings) | ❌ **lo único genuinamente nuevo** |
| Benchmarks de modelos | ❌ nuevo, pero barato una vez exista el corpus de evals |

**Conclusión:** el camino crítico es una sola cosa — la capa semántica (embeddings +
pgvector + 2 endpoints) — más un dataset que falta (barrios). Todo lo demás es
formalizar y publicar lo que ya funciona.

## Dónde vive

En este repo (**emap-labs**, privado — decisión 2026-07-07, sustituye al plan
inicial de vivir en emap-next): docs, evals y pipelines de datasets propios.
`packages/data-catalog` se queda en emap-next (es core del producto y su
paridad depende del monorepo); labs lo consume como repo hermano
(`../emap-next`), igual que emap-next consume el legacy. El código que emap
sirva en producción (p. ej. `packages/knowledge`, endpoints) nace en
emap-next con tier `lab`; aquí vive lo que no es producto: corpus, harness,
pipelines, benchmarks. Se hace público (o se extraen repos como
`emap-datasets`) en L4.

## Infra

- **Postgres + pgvector en el Hetzner** que ya pagas (corre OTP; OSRM pendiente).
  Privacy-first, coste cero adicional, sin límites de free tier. Supabase solo si
  el VPS se queda corto.
- **Embeddings y LLM por API** (modelos abiertos hosted: Mistral, Qwen vía
  proveedor barato, o local con Ollama para experimentar). **No se entrena nada.**

---

## Fases

Cada fase termina con algo **desplegado y consumido por EMAP en producción**.
Una fase a la vez; si una se alarga, se recorta alcance, no se solapa con la siguiente.

### L0 — Fundación (julio 2026, ~2 semanas)

Formalizar el catálogo y cerrar el dataset que falta.

1. ✅ (2026-07-07) `data-catalog`: `coverage` declarado en los 37 datasets y
   `quality` calculado por el nuevo CLI `python -m data_catalog quality`
   (registros, % campos vacíos, frescura vs `maxAgeDays`). 34/37 medibles,
   19.119 registros, 0 issues; paridad legacy intacta; 7 tests nuevos.
2. **Dataset de barrios**: límites de barrios de Bilbao + municipios de Bizkaia
   (opendata Euskadi / OSM admin boundaries) → `data/processed/neighborhoods/`.
   Es la unidad de agregación de todo lo que viene después ("qué barrio es más
   tranquilo" necesita saber qué es un barrio).
3. Primer **release versionado** de un dataset (POIs Euskadi + DEA + barrios,
   con los 6 metadatos) como artefacto descargable. Primer activo publicable.

*Hecho cuando:* `manifest.json` valida quality/coverage; capa de barrios visible
en el mapa; release v0.1 etiquetado en git.

### L1 — Corte vertical semántico (agosto–septiembre 2026)

El corazón de Labs. Un solo flujo, de punta a punta:

1. pgvector en el Hetzner; tabla de documentos (POIs, barrios, UrbanSignals
   agregados por barrio) con embeddings multilingües (ES/EU importa).
2. `POST /api/semantic-search`: "cafetería tranquila con enchufes cerca de Moyúa",
   "parque con sombra para ir con niños". Híbrido: filtro geo (packages/geo ya
   lo hace) + ranking vectorial.
3. `GET /api/nearby` estructurado (categoría + radio + señales) sobre la misma base.
4. **Consumido por el buscador de EMAP**: si la query no parece dirección,
   fallback a semantic-search. Feature visible para usuarios reales.
5. **Eval v0 desde el día uno**: 75–100 preguntas doradas con resultados esperados
   (mismo método que el golden de rutas). Sin esto no se puede iterar el ranking.
   → Borrador de 50 en `evals/semantic-golden-v0.yaml` (2026-07-07):
   anclas y nombres verificados contra los datasets; pendiente curación
   humana del euskera y ampliar a 75–100.

*Hecho cuando:* el buscador de emap-next.vercel.app responde consultas de intención
en ES y EU, y la eval corre en CI con precisión medida.

### L2 — Knowledge layer: explain-place (octubre–noviembre 2026)

Convertir las señales en respuestas.

1. Agregación de UrbanSignals por barrio: ruido proxy (incidencias históricas —
   las 73 celdas de hora punta ya existen), verde (arbolado/parques), servicios,
   transporte (paradas + frecuencias), pendiente media. → **score de barrio**
   con componentes explicables, no una caja negra.
2. `GET /api/explain-place`: contexto de un lugar o barrio en JSON + texto
   generado (LLM por API sobre los datos recuperados — RAG de verdad, citando
   señales). Responde "qué barrio es más tranquilo", "qué hay cerca y cómo llego".
3. Publicar el **esquema UrbanSignal + docs agent-readable** (llms.txt / MCP-ready).
   Es barato y es exactamente el tipo de activo que el borrador pedía.
4. En EMAP: tarjeta de lugar enriquecida con explain-place.

*Hecho cuando:* la tarjeta de lugar de producción muestra contexto generado con
citas de datos, y las respuestas pasan la eval (ampliada con casos explain-place).

### L3 — Evals de modelos + primer benchmark publicable (dic 2026 – ene 2027)

1. Harness `packages/evals`: corre el corpus L1+L2 contra 3–4 modelos abiertos
   (Qwen, Mistral, DeepSeek, Gemma — API u Ollama) midiendo precisión, latencia
   y coste por 1k consultas.
2. Elegir el modelo por datos y **publicar los resultados** (post/README):
   "benchmarks de inteligencia geográfica en euskera y español" — nadie más tiene
   esto y da credibilidad ante ayuntamientos e inversores.

*Hecho cuando:* tabla de resultados publicada y el modelo de producción elegido
por benchmark, no por vibes.

### L4 — Abrir y vender (feb–jun 2027)

Solo cuando L1–L3 estén en producción:

1. Extraer **emap-datasets** como repo público (pipelines + releases + docs).
   Primer OSS real de Labs.
2. **Piloto institucional**: propuesta a un ayuntamiento/diputación con lo que ya
   funciona (explain-place, accesibilidad, datos de barrio) — el dossier de
   inversores del legacy es la base. Un piloto, no tres.
3. **Kunoa reutiliza** `packages/knowledge` (recomendación/personalización) —
   segundo consumidor, que es el trigger para estabilizar APIs internas.
4. Preparar Euskadi completo (ESCALADO.md ya marca el camino; tráfico y aire ya
   cubren las 3 provincias).

---

## Reglas de cordura (para una persona)

- **Una fase a la vez.** Lo que no cabe, se recorta; no se paraleliza.
- **Cada fase acaba en producción consumida por EMAP.** Si EMAP no lo usa, no
  cuenta como hecho (dogfooding = la regla de decisión del borrador).
- **Evals antes que features semánticas**, igual que paridad antes que switch:
  es el método que ya funcionó en la migración.
- **Nada de repos/marca/web de Labs** hasta L4. Un doc y un tier `lab` bastan.
- **No entrenar modelos, no fine-tuning** en este horizonte. Revisar en jun 2027
  con los datos de L3 en la mano.
- QuestClub congelado; Kunoa solo como consumidor (no condiciona el diseño hasta L4).

## Qué se descarta del borrador fundacional (y por qué)

- *"Knowledge Layer" como proyecto separado* → es UrbanSignal + barrios + el
  índice vectorial. Emergerá de L1/L2; diseñarla aparte sería optimización prematura.
- *5 repos OSS (emap-rag, emap-evals, emap-sdk…)* → un repo (datasets) en L4;
  el resto cuando exista demanda externa real.
- *Supabase* → Postgres en el Hetzner propio (privacy-first, coste cero, sin lock-in).
- *Monetizar en 6 vías* → una: piloto institucional en L4. Las demás (APIs de pago,
  RAG privado, consultoría) se abren solas si el piloto funciona.
