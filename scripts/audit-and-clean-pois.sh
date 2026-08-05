#!/usr/bin/env bash
# Audita y limpia duplicados por proximidad en pois-euskadi.
# Estrategia: agrupa por celda ~100m (0.001°), se queda con el POI más completo
# (más tags, nombre más largo) y descarta los demás.
set -euo pipefail
NEXT="$(cd "$(dirname "$0")/../.." && pwd)/emap-next"
DATA="$NEXT/data/pois-euskadi"
cd "$DATA"

echo "=== ANTES ==="
for f in defib.json sports.json bikepark.json peaks.json; do
    n=$(python3 -c "import json; print(len(json.load(open('$f'))['pois']))")
    echo "  $f: $n POIs"
done

python3 << 'PYEOF'
import json
from collections import Counter
from pathlib import Path

DATA = Path(".")
LAYERS = {
    "defib.json": "defib",
    "sports.json": "sports",
    "bikepark.json": "bikepark",
    "peaks.json": "peaks",
}

for fname, layer in LAYERS.items():
    doc = json.loads(Path(fname).read_text())
    pois = doc["pois"]
    before = len(pois)

    # Agrupar por celda ~100m, quedarse con el más completo (más tags, nombre más largo)
    cells: dict[tuple, list[int]] = {}
    for i, p in enumerate(pois):
        key = (round(p["lat"], 3), round(p["lon"], 3))
        cells.setdefault(key, []).append(i)

    keep = []
    dropped = 0
    for key, indices in cells.items():
        if len(indices) == 1:
            keep.append(pois[indices[0]])
        else:
            # Ordenar por: tiene-EU, num tags, longitud nombre, tiene-id
            def score(idx):
                p = pois[idx]
                name = p["name"].get("es", p["name"]) if isinstance(p["name"], dict) else str(p["name"])
                has_eu = 1 if isinstance(p["name"], dict) and p["name"].get("eu") else 0
                n_tags = len(p.get("tags", {}))
                has_id = 1 if p.get("id") else 0
                return (has_eu, n_tags, len(name), has_id)
            best = max(indices, key=score)
            keep.append(pois[best])
            dropped += len(indices) - 1

    doc["pois"] = keep
    doc["count"] = len(keep)
    Path(fname).write_text(json.dumps(doc, ensure_ascii=False))
    print(f"{layer:12s}: {before:5d} → {len(keep):5d} POIs ({dropped} duplicados eliminados)")
PYEOF

echo "=== DESPUÉS ==="
for f in defib.json sports.json bikepark.json peaks.json; do
    n=$(python3 -c "import json; print(len(json.load(open('$f'))['pois']))")
    echo "  $f: $n POIs"
done

echo ""
echo "→ siguiente: regenerar el snapshot de evals con evals/sync-data.sh"
