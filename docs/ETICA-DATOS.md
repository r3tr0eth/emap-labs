# Ética de datos — emap / emap-labs

**Fecha:** 2026-07-08 · **Estado:** regla dura, no aspiración. Un PR que la
viole no se mergea.

emap describe el territorio para ayudar a moverse por él. Los datos urbanos
tienen historia de hacer lo contrario — del *redlining* a los mapas de "zonas
peligrosas" — y este documento existe para que emap nunca cruce esa línea.

## Reglas

1. **Infraestructura y entorno físico, jamás personas.** emap mide fuentes,
   paradas, bidegorris, tráfico, pendiente, iluminación, arbolado. **Nunca
   ingiere ni deriva**: criminalidad, renta, precio de vivienda, demografía,
   origen, "seguridad percibida" ni ningún proxy social. Si una señal ordena
   personas en vez de describir sitios, no entra — aunque la pida un cliente.

2. **Se puntúan rutas y coberturas, no barrios.** Una ruta es una elección
   efímera del usuario y se juzga por sus características físicas. Un número
   único que ordene barrios se lee como "barrios buenos y malos" mida lo que
   mida por dentro; por eso el índice compuesto por unidad administrativa
   (`coverage_index`) es **analítico/institucional** — sirve para señalar
   déficits de servicio público (la deuda de la administración con el barrio,
   no un juicio sobre él) — y **no se muestra en la UI de consumo**. En el
   producto, un barrio se describe con hechos: "3 fuentes · 12 paradas ·
   0,8 km de bidegorri".

3. **El sesgo de mapeo se declara, no se esconde.** OSM está mejor mapeado
   donde hay más renta y más perfil técnico; un conteo bajo puede significar
   "hay poco" o "está poco mapeado". Todo dataset derivado de OSM lo dice en
   su `coverage.notes`, y las cifras derivadas heredan la advertencia. La
   respuesta activa es el feedback loop: mapear mejor mejora la base de todos.

4. **Sin eufemismos sociales.** Las preguntas tipo "¿qué zona es más
   tranquila?" se responden con datos físicos nombrados como lo que son:
   `traffic` (incidencias históricas de tráfico), verde, ruido *medido* si
   algún día existe la fuente. Nunca "conflictivo", "seguro", "tranquilo"
   como etiqueta de un lugar habitado. Corolario de la regla de honestidad
   general del proyecto: *no se finge* — tampoco neutralidad que no se tiene.

5. **Cuidado con los bucles de refuerzo.** Si una función puede desviar
   sistemáticamente atención, visitas o inversión de las zonas peor servidas
   (p. ej. recomendar siempre "la zona con más servicios"), se revisa contra
   este documento antes de construirse. El caso de uso equidad (¿dónde falta
   inversión?) tiene prioridad sobre el caso de uso ranking.

## Aplicación práctica (estado actual)

- `neighborhood-scores`: renombrado a índice de **cobertura de
  infraestructura** (`coverage_index`); componente `calm` renombrado a
  `traffic`; conteos crudos siempre incluidos ("el score ordena, el número
  manda"). Uso institucional/analítico; la UI muestra hechos.
- Score visible en producto: **por ruta** (confort físico del trayecto), no
  por barrio.
- Corpus de evals: los casos "barrio más tranquilo para vivir" se mantienen
  como `answerable: false` — el sistema debe **rehusar el marco**, no
  responderlo con proxies.

Relacionado: regla de decisión de EMAP Labs (README), BRAND.md §7 (voz
honesta), coverage/quality en data-catalog.
