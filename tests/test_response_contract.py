import pytest

from response_contract import build_response, validate_response


def test_contract_answerable_includes_evidence_and_confidence():
    response = build_response(
        query="parking",
        runtime={"territory": "madrid", "territory_version": "0.3.0"},
        results=[{
            "id": "parking:p1",
            "tags": {"access_scope": "public"},
            "why": {
                "source": "Madrid",
                "source_url": "https://datos.madrid.es/source",
                "license": "CC-BY-4.0",
                "data_last_updated": "2026-08-28",
            },
            "data": {"freshness": "fresh", "retrieved_at": "2026-08-30T00:00:00Z"},
        }],
        detection={"detected": "parking", "confidence": 0.8},
        retriever="hybrid",
        took_ms=4,
        attribution="Ayuntamiento de Madrid (CC BY 4.0)",
    )
    assert response["schema_version"] == "intelligence.response.v1"
    assert response["answerable"] is True
    assert response["answer_status"] == "ANSWERED"
    assert response["evidence"][0]["source_url"].endswith("source")
    assert response["freshness"]["status"] == "fresh"
    assert response["confidence"]["level"] == "high"


def test_contract_distinguishes_unsupported_from_no_result():
    base = dict(
        query="x", runtime={"territory": "madrid", "territory_version": "0.3.0"},
        results=[], retriever="baseline", took_ms=1, attribution="Madrid",
    )
    unsupported = build_response(**base, detection={"detected": None, "confidence": 0})
    no_result = build_response(**base, detection={"detected": "parking", "confidence": 0.7})
    assert unsupported["limitations"] == ["UNSUPPORTED"]
    assert unsupported["answer_status"] == "UNSUPPORTED"
    assert no_result["limitations"] == ["NO_RESULT"]
    assert no_result["answer_status"] == "NO_RESULT"


def test_contract_abstains_when_detection_below_threshold():
    response = build_response(
        query="algo ambiguo",
        runtime={"territory": "euskadi", "territory_version": "0.2.0"},
        results=[],
        detection={"detected": "fountains", "confidence": 0.3,
                   "passed_threshold": False},
        retriever="hybrid", took_ms=1, attribution="Euskadi",
    )
    assert response["answer_status"] == "ABSTAINED"
    assert response["answerable"] is False
    assert response["abstained"] is True
    assert response["limitations"] == ["ABSTAINED"]


def test_contract_answered_with_stale_evidence_declares_limitation():
    response = build_response(
        query="parking",
        runtime={"territory": "madrid", "territory_version": "0.3.0"},
        results=[{"id": "parking:p1", "tags": {}, "why": {"source": "Madrid"},
                  "data": {"freshness": "stale"}}],
        detection={"detected": "parking", "confidence": 0.9},
        retriever="hybrid", took_ms=1, attribution="Madrid",
    )
    assert response["answer_status"] == "ANSWERED"
    assert response["freshness"]["status"] == "stale"
    assert "STALE_EVIDENCE" in response["limitations"]


def test_validate_response_rejects_contract_violations():
    valid = build_response(
        query="x", runtime={"territory": "madrid", "territory_version": "0.3.0"},
        results=[], retriever="baseline", took_ms=1, attribution="Madrid",
        detection={"detected": None, "confidence": 0},
    )
    validate_response(valid)  # el builder siempre produce contrato válido

    incompleto = {k: v for k, v in valid.items() if k != "evidence"}
    with pytest.raises(ValueError, match="faltan"):
        validate_response(incompleto)

    fuera_de_enum = dict(valid, answer_status="TERRITORY_REQUIRED")
    with pytest.raises(ValueError, match="answer_status"):
        validate_response(fuera_de_enum)

    incoherente = dict(valid, result={"items": [], "count": 3})
    with pytest.raises(ValueError, match="count"):
        validate_response(incoherente)


def test_contract_unknown_freshness_is_not_reported_as_fresh():
    response = build_response(
        query="x", runtime={"territory": "madrid", "territory_version": "0.3.0"},
        results=[{"id": "x", "tags": {}, "why": {"source": "unknown"},
                  "data": {"freshness": "unknown"}}],
        detection={"detected": "parking", "confidence": 0.6}, retriever="geo",
        took_ms=1, attribution="Madrid",
    )
    assert response["freshness"]["status"] == "unknown"
