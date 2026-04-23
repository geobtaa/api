import json
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_analytics_events_endpoint_queues_normalized_batch(async_client):
    payload = {
        "searches": [
            {
                "search_id": "search_123",
                "query": "maps",
                "page": 1,
                "per_page": 10,
                "results_count": 2,
                "zero_results": False,
            }
        ],
        "impressions": [
            {
                "search_id": "search_123",
                "resource_id": "stanford-abc123",
                "rank": 1,
                "page": 1,
                "view": "list",
            }
        ],
        "events": [
            {
                "event_id": "event_123",
                "event_type": "result_click",
                "search_id": "search_123",
                "resource_id": "stanford-abc123",
                "rank": 1,
            }
        ],
    }

    with patch("app.api.v1.endpoint_modules.analytics.write_analytics_batch.delay") as mock_delay:
        response = await async_client.post(
            "/api/v1/analytics/events",
            content=json.dumps(payload),
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Origin": "https://geo.btaa.org",
                "X-Visit-Token": "visit-123",
                "X-BTAA-Client-Name": "geoportal-web",
                "X-BTAA-Client-Version": "test-build",
                "X-BTAA-Client-Channel": "browser",
            },
        )

    assert response.status_code == 202
    mock_delay.assert_called_once()
    queued = mock_delay.call_args.args[0]
    assert queued["searches"][0]["visit_token"] == "visit-123"
    assert queued["searches"][0]["client_name"] == "geoportal-web"
    assert queued["searches"][0]["client_version"] == "test-build"
    assert queued["searches"][0]["client_channel"] == "browser"
    assert queued["searches"][0]["source_host"] == "geo.btaa.org"
    assert queued["impressions"][0]["visit_token"] == "visit-123"
    assert queued["events"][0]["client_name"] == "geoportal-web"


@pytest.mark.asyncio
async def test_analytics_events_endpoint_rejects_invalid_payload(async_client):
    response = await async_client.post(
        "/api/v1/analytics/events",
        content="not json",
        headers={"Content-Type": "text/plain;charset=UTF-8"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Invalid analytics payload"
