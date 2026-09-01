# Response Contract v1

`/search` y `/nearby` componen `intelligence.response.v1` en
`service/response_contract.py`. El builder valida cada respuesta con
`validate_response()` antes de devolverla: si la composición viola el
contrato, falla en el origen, no en un consumidor aguas abajo.

- `territory` y `territory_version`: runtime territorial que resolvió la petición.
- `answerable`: `true` solo si existe al menos un resultado respaldado por el
  índice. Coherente con `answer_status` por contrato validado.
- `answer_status`: `ANSWERED`, `NO_RESULT` (categoría detectada, corpus sin
  match), `ABSTAINED` (categoría detectada pero score bajo el umbral) o
  `UNSUPPORTED` (categoría no soportada). Evita colapsar todos los fallos en
  un único `answerable=false`. `STALE` y `CONFLICT` no son estados: lo stale
  se expresa vía `freshness` y `limitations`; la detección de evidencia
  contradictoria no está implementada.
- `result.items` / `result.count`: resultados normalizados del retrieval.
- `evidence`: fuente, URL, licencia, atribución, actualización, instante de
  ingesta, estado de freshness y entidades soportadas; deduplicada por
  (fuente, licencia, actualización).
- `freshness`: distribución de estados `fresh`, `stale` y `unknown` de los
  resultados; se calcula desde `source_updated` y el SLA del territorio (con
  fallback neutro, nunca el SLA de otro territorio).
- `confidence`: estructura explicable, no probabilidad calibrada. El score es
  el del detector semántico; los factores (`semantic_match`,
  `attribute_completeness`, `source_freshness`, `source_authority`) se
  reportan pero no se agregan al score.
- `limitations`: lista explícita. Una respuesta `ANSWERED` con freshness
  `stale` declara `STALE_EVIDENCE`; las no respondidas duplican su
  `answer_status`.
- `retrieval_method`: nombre real del retriever que sirvió la petición
  (p.ej. `baseline-keywords-geo`, `hybrid-keywords-then-minilm`,
  `geo-nearest` en `/nearby`).

Campos legacy al mismo nivel, mantenidos por compatibilidad con clientes
anteriores: `query`, `abstained`, `results`, `explanation`, `retriever`,
`reranked`, `took_ms`, `attribution`.

Errores explícitos de `/search` y `/nearby` (`429`, `503`, `404`/`422`
territoriales, `unsupported_layer`): todos devuelven `schema_version`,
`error` y `answerable: false`; `detail` solo en los territoriales (el 429
añade `retry_after_secs`/`limit`; `unsupported_layer` añade `layer`). No son
respuestas del contrato completo y no llevan `answer_status`. Los `422` de
validación de parámetros que genera FastAPI (falta `q`, `k` fuera de rango)
conservan su formato estándar `{"detail": [...]}`, y los endpoints de informe
(`/data-quality`, `/poi-freshness`) quedan fuera del contrato.

La respuesta no inventa disponibilidad en tiempo real. Pendiente para una
iteración posterior: factor de coincidencia geográfica en confidence,
detección de conflicto de evidencia y agregación determinista del score.
