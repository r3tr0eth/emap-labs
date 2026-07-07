#!/usr/bin/env bash
# Snapshot de los datasets que usan las evals → evals/data/ (committeable,
# para que CI no dependa de ../emap-next). Todo fuentes abiertas (ODbL/CC-BY).
set -euo pipefail
LABS="$(cd "$(dirname "$0")/.." && pwd)"
NEXT="$LABS/../emap-next/data"
OUT="$LABS/evals/data"

mkdir -p "$OUT/pois-euskadi" "$OUT/processed/pois"
cp "$NEXT"/pois-euskadi/{fountains,toilets,parking,bikepark,defib,beaches}.json "$OUT/pois-euskadi/"
cp "$NEXT"/processed/pois/{ev,cameras,metro,euskotren,cercanias,bilbobus,bizkaibus}.json "$OUT/processed/pois/"
du -sh "$OUT"
echo "snapshot actualizado — commitear evals/data/"
