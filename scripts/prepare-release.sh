#!/usr/bin/env bash
# Prepaqueta el benchmark para release pública (Zenodo/NLnet).
# Uso: ./scripts/prepare-release.sh [version]   (default: v2)
#
# Genera un directorio emap-labs-release/ con solo los ficheros relevantes
# para la publicación: código del harness, corpus curado, resultados más
# recientes y documentación. No modifica el repo (copia, no mueve).
set -euo pipefail
VERSION="${1:-v2}"
LABS="$(cd "$(dirname "$0")/.." && pwd)"
REL="$LABS/emap-labs-release-$VERSION"
rm -rf "$REL"

echo "→ empaquetando release $VERSION"

# Código del harness
mkdir -p "$REL/evals"
cp "$LABS/evals/run.py" "$REL/evals/"
cp "$LABS/evals/baseline.py" "$LABS/evals/semantic_local.py" "$REL/evals/"
cp "$LABS/evals/requirements.txt" "$REL/evals/"
cp "$LABS/evals/semantic-golden-v0.yaml" "$REL/evals/semantic-golden-v${VERSION}.yaml"

# Datos curados (snapshot)
cp -r "$LABS/evals/data" "$REL/evals/data"

# Resultados más recientes (solo los de la versión curada)
mkdir -p "$REL/results"
for f in \
  baseline-es-dev-2026-08-05.json \
  baseline-es-heldout-2026-08-05.json \
  baseline-eu-dev-2026-08-05.json \
  hybrid-e5large-es-dev-2026-08-05.json \
  hybrid-e5large-es-heldout-2026-08-05.json \
  hybrid-e5large-eu-dev-2026-08-05.json \
  hybrid-e5large-eu-heldout-2026-08-05.json \
  hybrid-minilm-es-dev-2026-08-05.json \
  hybrid-minilm-es-heldout-2026-08-05.json \
  hybrid-minilm-eu-dev-2026-08-05.json ; do
  cp "$LABS/evals/results/$f" "$REL/results/"
done

# Documentación
cp "$LABS/BENCHMARK.md" "$REL/"
cp "$LABS/CITATION.cff" "$REL/"
cp "$LABS/README.md" "$REL/README-emap-labs.md"
cp "$LABS/LICENSE" "$REL/" 2>/dev/null || true

# README de la release
DATE="2026-08-05"
if [ "$VERSION" != "v2" ]; then DATE="fecha"; fi
cat > "$REL/README.txt" <<EOF
EMAP Labs Benchmark v${VERSION} — ${DATE}
================================================================

Búsqueda semántica de infraestructura de movilidad en Euskadi.
139 casos curados, 22 capas, ES/EU en paridad.

Estructura:
  evals/        — harness de evaluación (run.py, baseline.py, semantic_local.py)
  evals/data/   — snapshot de los datasets para reproducir sin ../emap-next
  evals/semantic-golden-v${VERSION}.yaml — corpus dorado curado
  results/      — resultados más recientes por retriever e idioma
  BENCHMARK.md  — documentación completa del benchmark
  CITATION.cff  — metadatos de citación

Reproducir:
  pip install -r evals/requirements.txt
  python evals/run.py --retriever baseline --lang es
  python evals/run.py --retriever hybrid --lang es,eu --split heldout

DOI: 10.5281/zenodo.21282784
Licencia: código Apache-2.0, datos CC-BY-4.0 / ODbL
Atribución: © OpenStreetMap contributors + Open Data Euskadi + GTFS oficiales
EOF

echo "→ release empaquetada en: $REL"
echo "→ siguiente paso: subir a Zenodo (nueva versión del DOI 10.5281/zenodo.21282784)"
du -sh "$REL"
