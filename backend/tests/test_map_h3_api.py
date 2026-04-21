"""Tests for GET /api/v1/map/h3. Uses minimal app to avoid full stack (e.g. llm_service)."""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.map import router as map_router


def _make_app():
    app = FastAPI()
    app.include_router(map_router, prefix="/api/v1")
    return app


@patch("app.api.v1.endpoint_modules.map.map_h3_aggregation", new_callable=AsyncMock)
def test_map_h3_returns_resolution_hexes_global_count(mock_agg):
    # Compact facet-style [h3, count] tuples
    mock_agg.return_value = {
        "resolution": 5,
        "hexes": [["85083e1bfffffff", 12], ["85083e0ffffffff", 3]],
        "globalCount": 7,
    }
    client = TestClient(_make_app())
    resp = client.get(
        "/api/v1/map/h3",
        params={
            "q": "maps",
            "bbox": "-94,44,-92,46",
            "resolution": 5,
            "cache_bust": "unit-map-h3-api-resolution",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolution"] == 5
    assert isinstance(data["hexes"], list)
    assert len(data["hexes"]) == 2
    assert data["hexes"][0][0] == "85083e1bfffffff"
    assert data["hexes"][0][1] == 12
    assert data["globalCount"] == 7
    mock_agg.assert_called_once()
    call_kw = mock_agg.call_args[1]
    assert call_kw["q"] == "maps"
    assert call_kw["bbox"] == "-94,44,-92,46"
    assert call_kw["resolution"] == 5


@patch("app.api.v1.endpoint_modules.map.map_h3_aggregation", new_callable=AsyncMock)
def test_map_h3_empty_hexes(mock_agg):
    mock_agg.return_value = {"resolution": 4, "hexes": [], "globalCount": 0}
    client = TestClient(_make_app())
    resp = client.get(
        "/api/v1/map/h3",
        params={
            "bbox": "-94,44,-92,46",
            "resolution": 4,
            "cache_bust": "unit-map-h3-api-empty",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolution"] == 4
    assert data["hexes"] == []
    assert data["globalCount"] == 0


@patch("app.api.v1.endpoint_modules.map.map_h3_aggregation", new_callable=AsyncMock)
def test_map_h3_forwards_adv_q(mock_agg):
    mock_agg.return_value = {"resolution": 5, "hexes": [], "globalCount": 118}
    client = TestClient(_make_app())
    adv_q = (
        '[{"op":"AND","f":"dct_title_s","q":"water"},'
        '{"op":"AND","f":"dct_spatial_sm","q":"Pennsylvania"}]'
    )

    resp = client.get(
        "/api/v1/map/h3",
        params={
            "q": "",
            "adv_q": adv_q,
            "resolution": 5,
            "cache_bust": "unit-map-h3-api-advq",
        },
    )

    assert resp.status_code == 200
    call_kw = mock_agg.call_args[1]
    assert call_kw["adv_q"] == [
        {"op": "AND", "f": "dct_title_s", "q": "water"},
        {"op": "AND", "f": "dct_spatial_sm", "q": "Pennsylvania"},
    ]
