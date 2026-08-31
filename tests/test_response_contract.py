from response_contract import build_response


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


def test_contract_unknown_freshness_is_not_reported_as_fresh():
    response = build_response(
        query="x", runtime={"territory": "madrid", "territory_version": "0.3.0"},
        results=[{"id": "x", "tags": {}, "why": {"source": "unknown"},
                  "data": {"freshness": "unknown"}}],
        detection={"detected": "parking", "confidence": 0.6}, retriever="geo",
        took_ms=1, attribution="Madrid",
    )
    assert response["freshness"]["status"] == "unknown"
