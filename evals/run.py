#!/usr/bin/env python3
"""Harness de evals L1: corre el corpus dorado contra un retriever y puntúa.

    ../emap-next/.venv/bin/python evals/run.py [--retriever baseline] [--lang es|eu]

Métricas por caso según intent:
  nearest/attribute  hit@1 (el primer resultado cumple capa+radio+tags) y hit@k
  transit            el primer resultado es la estación/parada esperada
  semantic (answerable: false)  abstención correcta (el retriever devuelve [])

Guarda evals/results/<retriever>-<fecha>.json para comparar retrievers en el
tiempo (baseline hoy, pgvector en L1). El retriever nunca ve `expected`.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import BaselineRetriever  # noqa: E402

from emap_geo.distance import haversine_m  # noqa: E402

LABS = Path(__file__).resolve().parents[1]
EMAP_NEXT = (LABS / ".." / "emap-next").resolve()

# capa del corpus → fichero de datos en emap-next (todo pois[])
LAYER_FILES = {
    "fountains": "data/pois-euskadi/fountains.json",
    "toilets": "data/pois-euskadi/toilets.json",
    "parking": "data/pois-euskadi/parking.json",
    "bikepark": "data/pois-euskadi/bikepark.json",
    "defib": "data/pois-euskadi/defib.json",
    "beaches": "data/pois-euskadi/beaches.json",
    "ev": "data/processed/pois/ev.json",
    "cameras": "data/processed/pois/cameras.json",
    "metro": "data/processed/pois/metro.json",
    "euskotren": "data/processed/pois/euskotren.json",
    "cercanias": "data/processed/pois/cercanias.json",
    "bilbobus": "data/processed/pois/bilbobus.json",
    "bizkaibus": "data/processed/pois/bizkaibus.json",
}


def load_datasets() -> dict[str, list[dict]]:
    out = {}
    for layer, rel in LAYER_FILES.items():
        path = EMAP_NEXT / rel
        if not path.is_file():
            print(f"  aviso: falta {rel} — capa {layer} fuera", file=sys.stderr)
            continue
        out[layer] = json.loads(path.read_text())["pois"]
    return out


def find_poi(datasets, layer: str, *names: str) -> dict | None:
    for p in datasets.get(layer, []):
        if p["name"].get("es") in names or p["name"].get("eu") in names:
            return p
    return None


def resolve_anchor(case, datasets, landmarks) -> dict | None:
    a = case.get("anchor")
    if not a:
        return None
    if "landmark" in a:
        return dict(landmarks[a["landmark"]])
    poi = find_poi(datasets, a["layer"], a["name"], a.get("fallback_name", ""))
    if poi is None:
        raise SystemExit(f"{case['id']}: anchor irresoluble {a}")
    return {"lat": poi["lat"], "lon": poi["lon"]}


def norm(t: str) -> str:
    nfd = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def result_ok(r: dict, exp: dict, anchor: dict | None) -> bool:
    """¿Cumple un resultado concreto lo que expected exige?"""
    if r.get("layer") not in exp["layers"]:
        return False
    if "within_m" in exp:
        if not anchor:
            return False
        if haversine_m(anchor["lat"], anchor["lon"], r["lat"], r["lon"]) > exp["within_m"]:
            return False
    tags = r.get("tags", {})
    for k, v in exp.get("tags", {}).items():
        if tags.get(k) != v:
            return False
    for k, v in exp.get("tags_not", {}).items():
        if tags.get(k) is None or tags.get(k) == v:
            return False
    name_es = r["name"].get("es", "")
    if "name" in exp and name_es != exp["name"]:
        return False
    if "name_in" in exp and name_es not in exp["name_in"]:
        return False
    if "name_contains" in exp and norm(exp["name_contains"]) not in norm(name_es):
        return False
    lines = set((tags or {}).get("lines", []))
    if "answer_tags" in exp and set(exp["answer_tags"].get("lines", [])) != lines:
        return False
    if "answer_tags_min" in exp and not set(exp["answer_tags_min"].get("lines", [])) <= lines:
        return False
    return True


def failure_reason(r: dict, exp: dict, anchor: dict | None) -> str:
    """Por qué falla el top-1 — para análisis por categoría de fallo, no
    solo pasa/no-pasa (un evaluador vago sabotea el loop de mejora)."""
    if r.get("layer") not in exp["layers"]:
        return f"categoria_equivocada ({r.get('layer')})"
    if "within_m" in exp and anchor:
        d = haversine_m(anchor["lat"], anchor["lon"], r["lat"], r["lon"])
        if d > exp["within_m"]:
            return f"fuera_de_radio ({d:.0f}m > {exp['within_m']}m)"
    tags = r.get("tags", {})
    if any(tags.get(k) != v for k, v in exp.get("tags", {}).items()):
        return "atributo_incumplido"
    if any(tags.get(k) is None or tags.get(k) == v
           for k, v in exp.get("tags_not", {}).items()):
        return "atributo_incumplido"
    return "nombre_o_lineas"


def score_case(case, results, anchor) -> dict:
    if case.get("answerable") is False:
        ok = len(results) == 0
        return {"pass": ok, "reason": None if ok else "inventa",
                "detail": "abstiene" if ok else
                f"inventa: {results[0]['name'].get('es')}"}
    exp = case["expected"]
    need = exp.get("min_results", 1)
    hits = [r for r in results if result_ok(r, exp, anchor)]
    hit1 = bool(results) and result_ok(results[0], exp, anchor)
    ok = hit1 and len(hits) >= need
    reason = None if ok else (
        "abstencion_indebida" if not results
        else failure_reason(results[0], exp, anchor))
    top = results[0]["name"].get("es") if results else "∅"
    return {"pass": ok, "hit_at_k": len(hits) >= need, "reason": reason,
            "detail": f"top1={top}" + ("" if ok else f" ✗ {reason}")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", default="baseline",
                    choices=["baseline", "semantic", "hybrid"])
    ap.add_argument("--lang", default="es", choices=["es", "eu"])
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()

    corpus = yaml.safe_load((LABS / "evals/semantic-golden-v0.yaml").read_text())
    landmarks = yaml.safe_load((LABS / "evals/landmarks.yaml").read_text())
    datasets = load_datasets()
    if args.retriever == "semantic":
        from semantic_local import SemanticRetriever  # requiere .venv de labs
        retriever = SemanticRetriever(datasets)
    elif args.retriever == "hybrid":
        from semantic_local import HybridRetriever
        retriever = HybridRetriever(datasets)
    else:
        retriever = BaselineRetriever(datasets)

    rows, by_intent, gaps = [], {}, []
    for case in corpus["cases"]:
        anchor = resolve_anchor(case, datasets, landmarks)
        if hasattr(retriever, "set_anchor_names"):
            a = case.get("anchor") or {}
            retriever.set_anchor_names(
                [a.get("name", ""), a.get("fallback_name", ""), a.get("landmark", "")])
        results = retriever.retrieve(case["q"][args.lang], anchor, k=args.k)
        s = score_case(case, results, anchor)
        row = {"id": case["id"], "intent": case["intent"], **s}
        if case.get("known_gap"):
            # hueco de datos conocido: irresoluble para CUALQUIER retriever;
            # se reporta como inventario de datos que faltan, no como fallo
            row["known_gap"] = case["known_gap"]
            gaps.append(row)
            print(f"  ◌ {case['id']:28} {case['intent']:9} DATA GAP · {s['detail']}")
            continue
        rows.append(row)
        agg = by_intent.setdefault(case["intent"], [0, 0])
        agg[0] += s["pass"]
        agg[1] += 1
        mark = "✓" if s["pass"] else "✗"
        print(f"  {mark} {case['id']:28} {case['intent']:9} {s['detail']}")

    total = sum(r["pass"] for r in rows)
    print(f"\n{retriever.name} · lang={args.lang} · k={args.k}")
    for intent, (p, n) in sorted(by_intent.items()):
        print(f"  {intent:9} {p:>2}/{n}")
    print(f"  TOTAL     {total:>2}/{len(rows)}  ({100 * total // len(rows)}%)"
          f"  ·  {len(gaps)} huecos de datos conocidos")
    for g in gaps:
        print(f"    gap: {g['id']} — {g['known_gap']}")

    out_dir = LABS / "evals/results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{args.retriever}-{args.lang}-{date.today().isoformat()}.json"
    config = {}
    if args.retriever in ("semantic", "hybrid"):
        import semantic_local as sl
        config = {"model": sl.MODEL, "sim_threshold": sl.SIM_THRESHOLD,
                  "tie_window": sl.TIE_WINDOW}
    out.write_text(json.dumps({
        "retriever": retriever.name, "lang": args.lang, "k": args.k,
        "config": config, "n_corpus_cases": len(corpus["cases"]),
        "date": date.today().isoformat(), "corpus": corpus["version"],
        "total": {"pass": total, "cases": len(rows)},
        "by_intent": {i: {"pass": p, "cases": n} for i, (p, n) in by_intent.items()},
        "cases": rows,
        "known_gaps": gaps,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"  → {out.relative_to(LABS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
