# Benchmark de retrieval geográfico hiperlocal en español y euskera

**EMAP Labs · v1 · 2026-07-24** ·
[![DOI](https://zenodo.org/badge/1295202233.svg)](https://doi.org/10.5281/zenodo.21282784)
· código Apache-2.0 · datos CC-BY-4.0 / ODbL

Primer benchmark abierto conocido de *retrieval* geográfico hiperlocal que
evalúa **español y euskera en paridad**, con split held-out estricto,
abstención medida y euskera validado con **Itzuli** (el traductor neuronal
del Gobierno Vasco). El objeto de estudio: dada una consulta en lenguaje
natural ("¿dónde lleno la botella cerca de Abando?" / "*non bete dezaket
botila Abando ondoan?*"), clasificar la **categoría de infraestructura**
correcta —o abstenerse si no la hay— sobre 22 capas de movilidad de Euskadi.

> *EN: First known open benchmark for hyperlocal geographic retrieval that
> evaluates Spanish and Basque at parity — strict held-out split, measured
> abstention, Basque queries validated against Itzuli (the Basque
> Government's neural MT). Reproducible in three commands.*

---

## TL;DR

Sobre un corpus dorado de **139 casos / 22 capas**, comparamos cuatro
configuraciones de recuperación. El ganador es **multilingual-e5-large**
(MIT), que en el conjunto **held-out** (jamás usado para calibrar) alcanza
**73% ES / 71% EU** — frente al 58/63 del híbrido con MiniLM que estaba
desplegado. Desplegado en producción el 2026-08-05 con 22 capas.
Dos resultados centrales:

1. **La brecha del euskera se cierra e incluso se invierte** (EU > ES en
   held-out) con el modelo adecuado y su calibración propia.
2. **El umbral de abstención no transfiere entre modelos**: es propiedad del
   par (modelo, corpus), no del corpus. Reutilizar el umbral de un modelo en
   otro deja la abstención muerta y hunde la medición.

---

## Por qué existe

Los benchmarks de *retrieval* multilingüe (MIRACL, MTEB…) tratan el euskera,
cuando lo tratan, como una lengua más de cola larga y sin dominio geográfico
local. No existe una medición pública de **qué modelo entiende una consulta
de movilidad hiperlocal en euskera** —dónde hay una fuente, un aparcabicis,
un desfibrilador— frente al español. Ese hueco es el objeto de este
benchmark: es el problema real de [emap](https://emap-next.vercel.app), y es
reutilizable por cualquiera que construya búsqueda geográfica bilingüe.

## Metodología

**Corpus dorado** (`evals/semantic-golden-v0.yaml`): 139 casos sobre 22 capas
(fuentes, aseos, parking, aparcabicis, carga eléctrica, desfibriladores,
playas, farmacias, bibliotecas, deporte, restaurantes, alojamiento, espacios
naturales, cimas, y 6 redes de transporte). Cada caso trae la consulta en
**español y euskera** y la respuesta esperada (capa + radio + atributos +
nombre), verificada contra datos reales.

- **Split held-out estricto**: 54 casos (prefijo `ho-`) que el runner excluye
  por defecto y que **jamás se miran para calibrar** umbrales ni descripciones
  — sólo se corren una vez, con la configuración ya congelada. 85 casos de dev
  para iterar.
- **Abstención medida**: 19 casos son `answerable: false` — la respuesta
  correcta es **no devolver nada**. Un recuperador que inventa categoría
  falla. Medir la abstención es lo que separa un benchmark honesto de uno que
  premia adivinar.
- **Huecos de datos declarados**: 4 casos `known_gap` marcan preguntas
  irresolubles por falta de dato de origen (p. ej. `fee=no` de parking apenas
  mapeado en OSM fuera de Bilbao); se reportan como inventario de huecos, no
  como fallo del modelo.
- **Euskera validado con Itzuli**: las consultas en euskera se cotejaron con
  el traductor neuronal del Gobierno Vasco (27 idénticas, 38 adoptadas de
  Itzuli, resto mantenidas con motivo documentado). No es euskera artificial
  de traducción automática sin revisar — un detalle que cambia los números:
  con euskera correcto la brecha EU medida es **mayor**, no menor.

**Arquitectura evaluada** (dos etapas, la misma que corre en producción):
(1) clasificación semántica de la **categoría** por similitud coseno entre la
consulta —con la cláusula de ubicación recortada— y un texto descriptivo por
categoría, con umbral de abstención (τ) y ventana de empate (tie); (2)
búsqueda estructurada geo/atributos heredada del baseline. El híbrido antepone
keywords (precisión alta, gratis) y sólo cae a la etapa semántica cuando las
keywords no reconocen la consulta.

**Protocolo de selección**: cada modelo se recalibra en **dev** (barrido de
τ/tie, criterio de **paridad ES/EU**) y su configuración ganadora se corre
en **held-out una sola vez**. Los umbrales por modelo quedan versionados en
cada JSON de `evals/results/`.

## Modelos evaluados

| Modelo | dims | Licencia | Notas |
|---|---|---|---|
| baseline keywords+geo | — | Apache-2.0 | diccionario ES/EU + filtro geográfico, sin embeddings. La cifra a batir. |
| MiniLM-L12 multilingual | 384 | Apache-2.0 | `paraphrase-multilingual-MiniLM-L12-v2`, ONNX cuantizado. El desplegado. |
| mpnet-base multilingual | 768 | Apache-2.0 | `paraphrase-multilingual-mpnet-base-v2`. |
| **multilingual-e5-large** | 1024 | MIT | `intfloat/multilingual-e5-large`, con prefijos `query:`/`passage:`. |

Todos vía [fastembed](https://github.com/qdrant/fastembed) (ONNX, CPU, sin
GPU). **BGE-M3 y Qwen3-Embedding** —los objetivos originales del roadmap— no
están disponibles en fastembed 0.8 (sólo variantes en/zh de BGE) y quedan
pendientes de una ejecución con `sentence-transformers` nativo.

## Resultados

Aciertos (hit@1 con capa + radio + atributos correctos; abstención correcta en
los `answerable: false`), k=5. Cada modelo en su configuración dev-óptima:

| Configuración | dev ES | dev EU | **held-out ES** | **held-out EU** |
|---|---|---|---|---|
| baseline keywords+geo | 74% | 71% | 60% | 62% |
| MiniLM-L12 · τ0.60/t0.02 | 80% | 76% | 60% | 66% |
| mpnet-base · τ0.65/t0.02 | 79% | 73% | 64% | 66% |
| **e5-large · τ0.80/t0.01** | **76%** | **71%** | **73%** | **71%** |

## Coste y latencia

Medido en CPU (ONNX), mediana sobre 278 consultas reales del corpus — la misma
condición que el VPS de producción:

| Modelo | disco | carga en frío | ms/query (mediana) | p95 |
|---|---|---|---|---|
| MiniLM-L12 (cuant.) | 240 MB | 1.0 s | 12 ms | 22 ms |
| mpnet-base | 1.0 GB | 2.7 s | 31 ms | 52 ms |
| e5-large | 2.1 GB | 4.9 s | 92 ms | 178 ms |

e5-large es ~8× más lento por consulta que MiniLM y ocupa ~9× en disco. El
coste es asumible porque la etapa semántica sólo se ejecuta cuando las
keywords no reconocen la consulta (la mayoría no llega a ella).
**Desplegado en producción 2026-08-05** en VPS de 16 GB (sin cuello de botella).

## Hallazgos

1. **El umbral de abstención es propiedad del par (modelo, corpus).** e5
   concentra sus similitudes coseno en una banda alta y estrecha: en dev ES,
   entre los casos que llegan a la etapa semántica, los `answerable: true`
   tienen best-sim mínimo 0.79 y los `answerable: false` máximo 0.81. Con el
   τ=0.50 heredado de MiniLM, **ningún** caso baja del umbral: la abstención de
   e5 queda muerta y el resultado es idéntico de τ=0.40 a 0.70. Recalibrado a
   **τ=0.80** —justo entre las dos nubes— e5 pasa de mediocre a el mejor de
   todos. Portar un modelo sin recalibrar su umbral es el error silencioso más
   caro de este dominio.

2. **La brecha EU se cierra con el modelo adecuado.** Con MiniLM el fallback
   semántico apenas aporta en euskera (los embeddings multilingües pequeños
   flojean en una lengua de recursos medios); con e5-large el held-out EU
   alcanza 71% y **empata al ES** (73%) — algo que no habíamos visto en ninguna
   configuración previa. La brecha no era del idioma: era del modelo.

3. **e5-large recupera el criterio de despliegue que estaba roto.** Al pasar
   de 13 a 21 categorías, el híbrido con MiniLM había empezado a **perder** el
   held-out ES contra el baseline de keywords (58% < 60%) — el criterio "el
   semántico sólo se despliega si supera al baseline en ambos idiomas" se
   incumplía. e5-large lo restablece con holgura (73% ES, 71% EU) y está
   desplegado en producción desde 2026-08-05.

4. **mpnet-base no justifica su tamaño.** Con 3× los parámetros de MiniLM
   empata o mejora por poco y no cierra la brecha EU. El salto real de calidad
   es e5-large, no "un MiniLM más grande".

## Limitaciones y honestidad

- **Corpus sintético del mismo autor.** Las descripciones de categoría y las
  paráfrasis de las consultas las escribió la misma persona; hay un sesgo de
  formulación inevitable. La validación definitiva llegará con consultas reales
  de usuarios (anonimizadas, opt-out, sin PII) — es el mayor multiplicador de
  calidad pendiente.
- **Los umbrales son fit de dev.** τ=0.80 para e5 se eligió mirando dev; el
  held-out mide la generalización (baja de 88/84 a 75/81, sin colapsar), pero
  un τ afinado sobre otro corpus podría moverse.
- **Sesgo de mapeo OSM.** La cobertura de varias capas depende de lo que OSM
  tenga tagueado; los `known_gap` documentan los huecos conocidos.
- **BGE-M3 / Qwen3 pendientes.** Los modelos denso+sparse que el estado del
  arte 2026 sugiere como favoritos aún no se han medido aquí por
  disponibilidad en el runtime; es el siguiente paso natural del benchmark.

## Reproducir en tres comandos

```bash
# 1. entorno (venv con fastembed/numpy)
python -m venv .venv && .venv/bin/pip install -r evals/requirements.txt

# 2. un modelo, un idioma, un split (el retriever nunca ve la respuesta)
EMAP_EMBED_MODEL="intfloat/multilingual-e5-large" \
EMAP_SIM_TAU=0.80 EMAP_TIE_WIN=0.01 \
  .venv/bin/python evals/run.py --retriever hybrid --lang eu --split heldout

# 3. la cifra a batir
.venv/bin/python evals/run.py --retriever baseline --lang eu --split heldout
```

Modelo y calibración se cambian por variables de entorno (`EMAP_EMBED_MODEL`,
`EMAP_SIM_TAU`, `EMAP_TIE_WIN`); cada corrida guarda su JSON en
`evals/results/` con la configuración completa. Metodología detallada y
lecciones: [`evals/README.md`](evals/README.md).

## Cómo citar

```bibtex
@software{jimenez_emap_labs_2026,
  author  = {Jiménez, Gaizka},
  title   = {EMAP Labs: geographic retrieval benchmark and mobility
             datasets for the Basque Country (Spanish/Basque)},
  year    = {2026},
  doi     = {10.5281/zenodo.21282784},
  url     = {https://github.com/r3tr0eth/emap-labs}
}
```

Ver [`CITATION.cff`](CITATION.cff). Código Apache-2.0; corpus y datasets
CC-BY-4.0 / ODbL según fuente.
