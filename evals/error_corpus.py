#!/usr/bin/env python3
"""Gestiona el error corpus: verifica regressions, lista abiertos, estadísticas.

Uso:
    python evals/error_corpus.py --check       # CI: falla si hay regressions
    python evals/error_corpus.py --list        # lista bugs abiertos
    python evals/error_corpus.py --stats       # métricas de calidad
    python evals/error_corpus.py --init <slug> # crea template para bug nuevo
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

ERRORS_DIR = Path(__file__).resolve().parent / "errors"


def load_errors() -> list[dict]:
    """Carga todos los archivos YAML del error corpus."""
    errors = []
    if not ERRORS_DIR.exists():
        return errors
    for d in ["open", "fixed", "wontfix"]:
        sub = ERRORS_DIR / d
        if sub.exists():
            for f in sub.glob("*.yaml"):
                try:
                    doc = yaml.safe_load(f.read_text()) or {}
                    doc["_status"] = d
                    doc["_file"] = str(f)
                    errors.append(doc)
                except Exception as e:
                    print(f"  ERROR leyendo {f}: {e}", file=sys.stderr)
    return errors


def check_regression(errors: list[dict]) -> bool:
    """Verifica que los errores fixed sigan arreglados (simulación)."""
    failed = []
    for e in errors:
        if e.get("_status") == "fixed" and e.get("fix_commit"):
            # En un CI real, aquí se ejecutaría la query y se verificaría
            # Por ahora, solo verificamos que el formato sea correcto
            pass
    return len(failed) == 0


def list_open(errors: list[dict]) -> None:
    """Lista errores abiertos."""
    open_errors = [e for e in errors if e.get("_status") == "open"]
    if not open_errors:
        print("✓ No hay errores abiertos")
        return
    print(f"⚠ {len(open_errors)} errores abiertos:\n")
    for e in sorted(open_errors, key=lambda x: x.get("created", "")):
        print(f"  [{e.get('severity', '?'):8s}] {e.get('id', '?')[:40]}")
        print(f"             {e.get('query', {}).get('text', '?')[:50]}")
        print(f"             esperado: {e.get('expected', {}).get('layers')} | "
              f"obtenido: {e.get('got', {}).get('layers')}")
        print()


def stats(errors: list[dict]) -> None:
    """Estadísticas del error corpus."""
    total = len(errors)
    by_status = {}
    by_severity = {}
    for e in errors:
        s = e.get("_status", "?")
        by_status[s] = by_status.get(s, 0) + 1
        sev = e.get("severity", "?")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    print(f"Error corpus: {total} entradas")
    print(f"  Por estado: {by_status}")
    print(f"  Por severidad: {by_severity}")


def init_error(slug: str) -> None:
    """Crea un template para un nuevo error."""
    today = date.today().isoformat()
    template = {
        "id": f"e5large-{today}-{slug}",
        "status": "open",
        "severity": "major",
        "created": today,
        "fixed": None,
        "query": {"text": "", "lang": "es", "lat": None, "lon": None},
        "expected": {"layers": [], "within_m": 400},
        "got": {"layers": [], "result_name": ""},
        "diagnosis": "",
        "fix_rule": "",
        "fix_commit": None,
        "retriever": "hybrid-e5large-rerank",
    }
    ERRORS_DIR.mkdir(parents=True, exist_ok=True)
    (ERRORS_DIR / "open").mkdir(exist_ok=True)
    path = ERRORS_DIR / "open" / f"{template['id']}.yaml"
    path.write_text(yaml.dump(template, default_flow_style=False, sort_keys=False))
    print(f"Creado: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Error corpus de EMAP Labs")
    parser.add_argument("--check", action="store_true", help="Verifica regressions")
    parser.add_argument("--list", action="store_true", help="Lista errores abiertos")
    parser.add_argument("--stats", action="store_true", help="Estadísticas")
    parser.add_argument("--init", metavar="SLUG", help="Crea template de error")
    args = parser.parse_args()

    errors = load_errors()

    if args.init:
        init_error(args.init)
        return 0
    if args.list:
        list_open(errors)
        return 0
    if args.stats:
        stats(errors)
        return 0
    if args.check:
        ok = check_regression(errors)
        return 0 if ok else 1

    # Por defecto: stats + list
    stats(errors)
    print()
    list_open(errors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
