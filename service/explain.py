"""Módulo de explicabilidad para el servicio semántico.

Genera explicaciones de por qué se devolvió cada resultado:
- categoría detectada y confianza
- alternativas descartadas
- fuente y frescura del datos
- distancia y atributos coincidentes
"""
from __future__ import annotations

from typing import Mapping


def source_metadata(document: Mapping | None) -> dict:
    """Extrae evidencia de una capa ya perteneciente al runtime resuelto."""
    document = document or {}
    return {
        "source": document.get("source", document.get("source_id", "unknown")),
        "license": document.get("license", "unknown"),
        "last_updated": document.get("source_updated"),
    }


def explain_result(
    result: dict,
    query: str,
    anchor: dict | None,
    category_scores: dict[str, float],
    threshold: float,
    source_document: Mapping | None = None,
) -> dict:
    """Genera la explicación para un resultado individual."""
    layer = result["layer"]
    source = source_metadata(source_document)

    explanation = {
        "category": layer,
        "source": source["source"],
        "source_url": source_document.get("source_url") if source_document else None,
        "license": source["license"],
    }

    if source["last_updated"]:
        explanation["data_last_updated"] = source["last_updated"]

    if anchor and "distance_m" in result:
        explanation["distance_m"] = result["distance_m"]

    # Tags relevantes que coinciden con la consulta
    tags = result.get("tags", {})
    if tags:
        matching_tags = {k: v for k, v in tags.items()
                        if any(t in query.lower() for t in k.lower().split("_"))}
        if matching_tags:
            explanation["matching_attributes"] = matching_tags

    return explanation


def explain_detection(
    detected_layers: list[str],
    category_scores: dict[str, float],
    threshold: float,
    method: str,
) -> dict:
    """Explica cómo se detectó la categoría."""
    if not category_scores:
        return {
            "detected": None,
            "method": method,
            "confidence": 0.0,
            "threshold": threshold,
            "alternatives": [],
            "note": "no_category_detected",
        }

    sorted_scores = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    best_layer = sorted_scores[0][0] if sorted_scores else None
    best_score = sorted_scores[0][1] if sorted_scores else 0.0

    # Alternativas: categorías cercanas al mejor (dentro de 0.15)
    alternatives = [
        {"layer": layer, "score": round(score, 3),
         "margin": round(score - best_score, 3)}
        for layer, score in sorted_scores[1:]
        if score >= best_score - 0.15
    ][:3]  # top 3 alternativas

    return {
        "detected": best_layer,
        "method": method,
        "confidence": round(best_score, 3),
        "threshold": threshold,
        "passed_threshold": best_score >= threshold,
        "alternatives": alternatives,
        "all_scores": {layer: round(score, 3) for layer, score in sorted_scores},
    }
