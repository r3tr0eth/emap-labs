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
import hashlib
import json
import os
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import BaselineRetriever  # noqa: E402

try:
    from emap_geo.distance import haversine_m  # noqa: E402
except ImportError:  # CI / entorno sin emap-next: fallback vendorizado
    from _geo import haversine_m  # noqa: E402

LABS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LABS))
from regions import Territory, load_territory  # noqa: E402
from retriever_config import profile_names  # noqa: E402


def _data_root() -> Path:
    """EMAP_EVAL_DATA > snapshot local (evals/data, CI) > ../emap-next/data."""
    env = os.environ.get("EMAP_EVAL_DATA")
    if env:
        return Path(env)
    snapshot = LABS / "evals" / "data"
    if snapshot.is_dir():
        return snapshot
    return (LABS / ".." / "emap-next" / "data").resolve()


DATA_ROOT = _data_root()


def result_filename(
    retriever: str,
    model_tag: str,
    territory: str,
    lang: str,
    split: str,
    run_date: date,
) -> str:
    """Nombre inequívoco del artefacto; dos territorios nunca se pisan."""
    tag = f"-{model_tag}" if model_tag else ""
    return f"{retriever}{tag}-{territory}-{lang}-{split}-{run_date.isoformat()}.json"


def load_datasets(territory: Territory) -> dict[str, list[dict]]:
    out = {}
    for layer, rel in territory.layers.items():
        path = DATA_ROOT / rel
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
    ap.add_argument("--territory", default="euskadi",
                    help="id de regions/<id>/region.yaml")
    ap.add_argument("--profile", choices=profile_names(),
                    help="perfil versionado de modelo + calibración")
    ap.add_argument("--output-dir", type=Path,
                    default=LABS / "evals/results",
                    help="directorio de resultados (útil para CI y QA aislada)")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--min-pass", type=float, default=None,
                    help="%% mínimo de aciertos; por debajo, exit 1 (gate de CI)")
    ap.add_argument("--split", default="dev",
                    choices=["dev", "heldout", "challenge", "all"],
                    help="dev: casos de desarrollo (default). heldout: split "
                         "original congelado — gate duro. challenge: casos "
                         "nuevos añadidos post-calibración — informativo. "
                         "all: todos los casos.")
    args = ap.parse_args()

    territory = load_territory(args.territory)
    corpus_path = territory.evaluation_path("corpus")
    corpus_sha256 = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    corpus = yaml.safe_load(corpus_path.read_text())
    if args.split != "all":
        corpus["cases"] = [c for c in corpus["cases"]
                           if c.get("split", "dev") == args.split]
    if not corpus["cases"]:
        raise SystemExit(f"corpus {territory.id}: split '{args.split}' sin casos")
    missing_lang = [c["id"] for c in corpus["cases"]
                    if args.lang not in (c.get("q") or {})]
    if missing_lang:
        raise SystemExit(
            f"corpus {territory.id} no soporta lang '{args.lang}': "
            f"{len(missing_lang)} casos sin consulta (p.ej. {missing_lang[0]})"
        )
    landmarks = yaml.safe_load(territory.evaluation_path("landmarks").read_text())
    datasets = load_datasets(territory)
    if args.profile:
        os.environ["EMAP_RETRIEVER_PROFILE"] = args.profile
    if args.retriever == "semantic":
        from semantic_local import SemanticRetriever  # requiere .venv de labs
        retriever = SemanticRetriever(datasets, profile_name=args.profile)
    elif args.retriever == "hybrid":
        from semantic_local import HybridRetriever
        retriever = HybridRetriever(datasets, profile_name=args.profile)
    else:
        retriever = BaselineRetriever(datasets)

    rows, by_intent, gaps = [], {}, []
    latencies_ms: list[float] = []
    for case in corpus["cases"]:
        anchor = resolve_anchor(case, datasets, landmarks)
        if hasattr(retriever, "set_anchor_names"):
            a = case.get("anchor") or {}
            retriever.set_anchor_names(
                [a.get("name", ""), a.get("fallback_name", ""), a.get("landmark", "")])
        t0 = time.perf_counter()
        results = retriever.retrieve(case["q"][args.lang], anchor, k=args.k)
        latencies_ms.append((time.perf_counter() - t0) * 1000)
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
    score_pct = 100 * total // len(rows) if rows else 0
    print(f"  TOTAL     {total:>2}/{len(rows)}  ({score_pct}%)"
          f"  ·  {len(gaps)} huecos de datos conocidos")
    for g in gaps:
        print(f"    gap: {g['id']} — {g['known_gap']}")

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {}
    model_tag = ""  # sufijo de modelo para no pisar resultados entre modelos
    if args.retriever in ("semantic", "hybrid"):
        # La verdad sale del encoder que ejecutó, no de constantes de módulo:
        # el artefacto no puede volver a declarar un modelo distinto del usado.
        encoder = retriever.encoder
        config = {"profile": encoder.profile_name, "model": encoder.model,
                  "sim_threshold": encoder.sim_threshold,
                  "tie_window": encoder.tie_window}
        model_tag = encoder.profile_name
    out = out_dir / result_filename(
        args.retriever,
        model_tag,
        territory.id,
        args.lang,
        args.split,
        date.today(),
    )
    out.write_text(json.dumps({
        "retriever": retriever.name, "territory": territory.id,
        "lang": args.lang, "k": args.k,
        "config": config, "n_corpus_cases": len(corpus["cases"]),
        "date": date.today().isoformat(), "corpus": corpus["version"],
        "corpus_sha256": corpus_sha256,
        "latency_ms": {
            "avg": round(sum(latencies_ms) / len(latencies_ms), 1),
            "max": round(max(latencies_ms), 1),
            "total": round(sum(latencies_ms)),
        } if latencies_ms else None,
        "total": {"pass": total, "cases": len(rows)},
        "by_intent": {i: {"pass": p, "cases": n} for i, (p, n) in by_intent.items()},
        "cases": rows,
        "known_gaps": gaps,
    }, ensure_ascii=False, indent=2) + "\n")
    try:
        shown_out = out.relative_to(LABS)
    except ValueError:
        shown_out = out
    print(f"  → {shown_out}")
    pct = 100 * total / len(rows) if rows else 0
    if args.min_pass is not None and pct < args.min_pass:
        print(f"GATE: {pct:.0f}% < mínimo exigido {args.min_pass:.0f}%")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
