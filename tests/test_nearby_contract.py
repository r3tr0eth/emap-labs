from response_contract import build_response


def test_nearby_response_keeps_geo_method_and_evidence():
    response = build_response(
        query="nearby:fountains",
        runtime={"territory": "madrid", "territory_version": "0.3.0"},
        results=[{
            "id": "fountains:f1", "name": {"es": "Fuente"},
            "layer": "fountains", "distance_m": 42, "tags": {},
            "why": {"source": "Madrid", "source_url": "https://datos.madrid.es",
                    "license": "CC-BY-4.0", "data_last_updated": "2026-08-30"},
            "data": {"freshness": "fresh", "retrieved_at": "2026-08-30T00:00:00Z"},
        }],
        detection={"detected": "fountains", "method": "geo", "confidence": 1.0},
        retriever="geo-nearest", took_ms=1, attribution="Madrid CC BY",
    )
    assert response["retrieval_method"] == "geo-nearest"
    assert response["result"]["items"][0]["distance_m"] == 42
    assert response["evidence"][0]["entities"] == ["fountains:f1"]
