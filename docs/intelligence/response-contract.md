# Response Contract v1

`/search` y `/nearby` componen `intelligence.response.v1` en
`service/response_contract.py`.
Los campos `results`, `abstained` y `retriever` se mantienen por compatibilidad
con clientes anteriores.

- `territory` y `territory_version`: runtime territorial que resolvió la petición.
- `answerable`: `true` solo si existe al menos un resultado respaldado por el
  índice.
- `answer_status`: `ANSWERED`, `NO_RESULT`, `ABSTAINED` (categoría detectada
  pero score bajo) o `UNSUPPORTED` (categoría no soportada). Evita colapsar
  todos los fallos en un único `answerable=false`.
- `result.items` / `result.count`: resultados normalizados del retrieval.
- `evidence`: fuente, URL, licencia, atribución, actualización, instante de
  ingesta, estado de freshness y entidades soportadas.
- `freshness`: distribución de estados `fresh`, `stale` y `unknown` de los
  resultados; se calcula desde `source_updated` y el SLA del dataset.
- `confidence`: estructura explicable, no probabilidad calibrada. El score y
  los factores proceden del detector, presencia de atributos, freshness y
  autoridad de fuente.
- `retrieval_method`: perfil real (`baseline`, `semantic` o `hybrid`).

La respuesta no inventa disponibilidad en tiempo real. Una fuente stale o una
restricción sin evidencia debe conducir a una limitación explícita y será
objeto de la siguiente iteración de abstention formal.
