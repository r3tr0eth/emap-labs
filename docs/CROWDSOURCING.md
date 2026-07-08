# Crowdsourcing en emap — análisis y plan (2026-07-08)

Marco cultural: esto en Euskadi se llama **auzolan** (trabajo comunal) — el
framing correcto para producto, comunidad y convocatorias. Marco técnico:
`UrbanSignal` ya tiene campo `confidence`, y emap ya tiene un feedback loop
vivo ("¿Un error en el mapa? Repórtalo a OSM").

## Beneficios (por qué sí)

1. **Frescura donde lo oficial llega tarde**: la fuente seca, el aseo
   cerrado, el aparcabicis retirado — exactamente el "saber cosas de la
   calle" que es nuestra tesis. Es una red de sensores que no pagamos.
2. **Corrección activa del sesgo de mapeo** (ETICA-DATOS §3): la respuesta
   honesta a "OSM mapea mejor donde hay renta" es facilitar que se mapee lo
   demás — el auzolan de datos es la mitigación, no solo la declaración.
3. **Comunidad como foso**: usuarios que contribuyen se quedan; y es la
   historia que NLnet (commons), BIND (ciudadanía) y diputaciones (ciencia
   ciudadana) quieren financiar.

## Peligros (por qué con cuidado) — y su mitigación

| Peligro | Realidad para nosotros | Mitigación |
|---|---|---|
| **Vandalismo/spam** | una persona no puede moderar una cola | v1 sin texto libre: SOLO taps estructurados (👍/👎, opciones cerradas); rate-limit por hash+día; k≥3 confirmaciones antes de mostrar efecto |
| **Dato erróneo con daño real** | DEA y montaña son seguridad: un DEA mal ubicado en una emergencia es grave | **capas de seguridad inmunes al crowd**: DEA, dificultad de senderos y similares solo datos oficiales; el crowd puede como mucho *bajar confianza* con aviso, nunca mover/borrar |
| **Privacidad del contribuidor** | reportes = (ubicación, hora) del usuario → trazas de movimiento | sin cuentas; sin PII; agregación antes de publicar; hash de rate-limit con TTL corto; publicación diferida. GDPR casi trivial: no hay nada que borrar |
| **Contaminación de licencias** | mezclar contribuciones propias con ODbL crea un fork legal del commons | regla: los HECHOS nuevos van a OSM (flujo in-app hacia nota/edición OSM — ya existe); nosotros solo guardamos *señales de confianza* efímeras sobre datos existentes, declaradas ODbL-compatibles/CC0 en el momento de contribuir |
| **Reproducir el sesgo** | el crowd es gente con smartphone y hábito digital — el mismo sesgo de OSM | el crowd ajusta *confianza/frescura*, nunca decide *cobertura*; los análisis de equidad (coverage_index) siguen siendo solo-oficial |
| **Sala vacía** | crowdsourcing sin usuarios = UI muerta que estorba | secuenciar: nada always-on hasta tener uso real; mientras, campañas acotadas |
| **Gaming comercial** | falsos reportes interesados (competencia entre negocios) | no hacemos reseñas ni estados de negocios; solo infraestructura pública → exposición mínima |

## Plan por fases

**v0 — ya en producción (coste 0):** el funnel a OSM ("repórtalo a OSM"
abre nota georreferenciada). Mejora el commons, cero moderación, cero
responsabilidad nuestra. Mantener y hacerlo más visible.

**v1 — confirmaciones estructuradas (cuando haya usuarios reales):**
en el popup de un POI: *"¿Funciona esta fuente?"* 👍/👎. Cada tap es un
evento `confidence` de UrbanSignal: anónimo, k≥3 para surtir efecto,
decaimiento temporal, y el efecto es SIEMPRE honesto y reversible —
*"reportada como seca hace 3 días"*, nunca borrar el dato. Sin texto libre,
sin fotos (moderación), sin cuentas. Capas de seguridad excluidas.

**v2 — auzolan organizado (con socio institucional):** campañas acotadas
de accesibilidad con el esquema **OpenSidewalks** (bordillos, escaleras,
anchos de acera) junto a asociaciones/diputación: eventos con principio y
fin (moderación acotada), socio que comparte responsabilidad, y el dato
resultante alimenta el caso de uso equidad. Es la versión con mejor ratio
valor/riesgo y la más financiable.

**v2.5 — mendi con pinzas:** estado de senderos ("embarrado", "puente
cerrado") solo como *aviso de baja confianza con fecha*, jamás como dato de
dificultad; disclaimer siempre.

**Implícito continuo:** las queries anonimizadas del buscador (ya en
roadmap) son crowdsourcing pasivo — la mayor fuente de verdad sobre qué
necesita la gente, sin pedirle nada.

## Reglas duras (extienden ETICA-DATOS.md)

1. El crowd ajusta **confianza y frescura**; los hechos nuevos van a OSM.
2. Capas de seguridad (DEA, dificultad de montaña) inmunes al crowd.
3. Sin cuentas, sin PII, sin texto libre en v1; k-anonimato antes de efecto.
4. Toda señal crowd se muestra con su edad y reversibilidad ("hace N días").
5. Los análisis institucionales de equidad no consumen señales crowd.
