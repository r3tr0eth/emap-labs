"""Contrato común de respuesta para EMAP Intelligence.

El builder no hace retrieval ni decide hechos: compone señales ya calculadas
por el runtime y mantiene el contrato anterior para compatibilidad.
"""
from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

SCHEMA_VERSION = "intelligence.response.v1"


def _confidence(detection: Mapping, results: Sequence[Mapping]) -> dict:
    score = float(detection.get("confidence") or 0.0)
    freshness = [((r.get("data") or {}).get("freshness")) for r in results]
    freshness = [s for s in freshness if s]
    factors = {
        "semantic_match": round(score, 3),
        "attribute_completeness": round(sum(bool(r.get("tags")) for r in results) / len(results), 3)
        if results else 0.0,
        "source_freshness": round(sum(s == "fresh" for s in freshness) / len(freshness), 3)
        if freshness else 0.0,
        "source_authority": round(sum(bool((r.get("why") or {}).get("source")) for r in results) / len(results), 3)
        if results else 0.0,
    }
    if not results:
        level = "low"
    elif score >= 0.75 and factors["source_freshness"] >= 0.5:
        level = "high"
    elif score >= 0.5:
        level = "medium"
    else:
        level = "low"
    return {"level": level, "score": round(score, 3), "factors": factors}


def build_response(*, query: str, runtime: Mapping, results: Sequence[Mapping],
                   detection: Mapping, retriever: str, took_ms: int,
                   attribution: str) -> dict:
    """Compone la respuesta v1 y deja campos legacy al mismo nivel."""
    answerable = bool(results)
    if answerable:
        answer_status = "ANSWERED"
        limitations: list[str] = []
    elif detection.get("detected"):
        answer_status = "ABSTAINED" if detection.get("passed_threshold") is False else "NO_RESULT"
        limitations = [answer_status]
    else:
        answer_status = "UNSUPPORTED"
        limitations = ["UNSUPPORTED"]
    freshness_states = Counter((r.get("data") or {}).get("freshness", "unknown") for r in results)
    evidence = []
    evidence_by_key = {}
    for result in results:
        why = result.get("why") or {}
        key = (why.get("source"), why.get("license"), why.get("data_last_updated"))
        current = evidence_by_key.get(key)
        if current is not None:
            entity_id = result.get("id")
            if entity_id not in current["entities"]:
                current["entities"].append(entity_id)
            continue
        item = {
            "source": why.get("source", "unknown"),
            "source_url": why.get("source_url"),
            "attribution": attribution,
            "license": why.get("license", "unknown"),
            "source_updated": why.get("data_last_updated"),
            "retrieved_at": result.get("data", {}).get("retrieved_at"),
            "freshness": result.get("data", {}).get("freshness", "unknown"),
            "entities": [result.get("id")],
        }
        evidence_by_key[key] = item
        evidence.append(item)
    if freshness_states.get("stale"):
        freshness_status = "stale"
    elif freshness_states.get("fresh"):
        freshness_status = "fresh"
    else:
        freshness_status = "unknown"
    return {
        "schema_version": SCHEMA_VERSION,
        "territory": runtime["territory"],
        "territory_version": runtime["territory_version"],
        "answerable": answerable,
        "answer_status": answer_status,
        "result": {"items": list(results), "count": len(results)},
        "evidence": evidence,
        "freshness": {"states": dict(freshness_states), "status": freshness_status},
        "confidence": _confidence(detection, results),
        "limitations": limitations,
        "retrieval_method": retriever,
        # Legacy fields: web/MCP clients already consume these.
        "query": query,
        "abstained": not answerable,
        "results": list(results),
        "explanation": detection,
        "retriever": retriever,
        "reranked": False,
        "took_ms": took_ms,
        "attribution": attribution,
    }
