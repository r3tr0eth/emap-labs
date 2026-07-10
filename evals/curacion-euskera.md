# Curación del euskera — registro de validación

**Estado: VALIDADO con Itzuli (traductor neuronal del Gobierno Vasco), 2026-07-08.**

Método: las 112 queries (sin `robust-*`, cuyas erratas son deliberadas) se
tradujeron ES→EU con Itzuli vía copy-paste (bloques en `itzuli-bloques.md`)
y se cotejaron contra el corpus con veredicto por caso:

- **27 idénticas** — validadas sin cambio.
- **38 adoptadas de Itzuli** — genitivos, léxico y giros suyos mejores
  (p. ej. `Alde Zaharrean` por `Zazpikaleetan`, `-tzako`, `Bizkaibusen
  geltokia`, `aldiriak` para Cercanías).
- **6 ajustes combinados** — corrección gramatical manteniendo forma de
  búsqueda directa (no subordinada).
- **41 mantenidas con motivo** — Itzuli malinterpretó (candar→`txanda`,
  chapuzón→`txapligu`, Doña Casilda→`Casilda andrea`, cámara→`ganbera`,
  acabo de correr→`hasi berria`) o devolvió subordinadas/nominalizaciones
  que nadie teclea (`...dudan`, `...den`, `...tzea`); también se conservó
  `DEA` frente a `KDA` (ambas reales; DEA es lo rotulado en los aparatos)
  y `bizikleta-aparkaleku` donde Itzuli perdía el matiz bici/coche.

Impacto medido: dev EU 75→73 (baseline) y 71→70 (híbrido); held-out EU
67→66 y 69→66. El euskera artificial previo inflaba los resultados.

Pendiente de lujo (no bloquea): 30 min de revisión nativa (HiTZ/Librezale)
sobre las 41 mantenidas, y queries reales anonimizadas cuando haya uso.

**Ampliación ep-\* (2026-07-09): VALIDADA con Itzuli el mismo día** (BLOQUE
6). De 16 queries: 9 idénticas (o solo coma), **5 adoptadas de Itzuli**
(farmazia "Moyua inguruan", "frontoia" por pilotalekua, "botikak" por
sendagaiak, "lo egiteko leku bat gaur gauean…", genitivo "biosferaren"),
1 ajuste combinado ("ikasteko aretoa…" — el orden literal de Itzuli, con
coma, no es una query realista). Hallazgos aplicados: keyword `frontoi`
añadida al baseline (el "frontoia" de Itzuli no casaba con "fronton");
"botikak" hace que en EU la consulta de medicamentos sea alcanzable por
keywords (proximidad léxica farmacia/medicina real del euskera).
Pendiente menor: cotejar el texto EU de las 8 descripciones de categoría
nuevas de `semantic_local.py` (no son queries de usuario).

**Ampliación md-\* (2026-07-10, PENDIENTE de Itzuli):** los 6 casos mendi
llevan euskera de borrador propio. BLOQUE 7 en `itzuli-bloques.md`.
