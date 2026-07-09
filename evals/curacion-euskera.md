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

**Ampliación ep-\* (2026-07-09, PENDIENTE de Itzuli):** los 16 casos nuevos
de euskadi-places llevan euskera de borrador propio (no validado). Antes de
darlos por curados: pasar el BLOQUE 6 de `itzuli-bloques.md` por Itzuli y
cotejar. Lo mismo aplica al texto EU de las 8 descripciones de categoría
nuevas en `semantic_local.py`.
