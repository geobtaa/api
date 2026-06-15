from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.analytics import router


def test_analytics_events_accepts_cli_command_payload(monkeypatch):
    captured = {}

    class FakeTask:
        def delay(self, payload):
            captured["payload"] = payload

    monkeypatch.setattr("app.api.v1.endpoint_modules.analytics.write_analytics_batch", FakeTask())

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post(
        "/api/v1/analytics/events",
        headers={
            "X-BTAA-Client-Name": "btaa-geo-api-cli",
            "X-BTAA-Client-Version": "0.1.0",
            "X-BTAA-Client-Channel": "cli",
            "X-BTAA-Client-Instance": "instance-1",
        },
        json={
            "events": [
                {
                    "event_id": "event-1",
                    "event_type": "cli.command.search",
                    "properties": {"command": "search"},
                }
            ],
            "searches": [
                {
                    "search_id": "search-1",
                    "query": "water",
                    "view": "cli",
                    "results_count": 1,
                }
            ],
        },
    )

    assert response.status_code == 202
    event = captured["payload"]["events"][0]
    search = captured["payload"]["searches"][0]
    assert event["event_type"] == "cli.command.search"
    assert event["client_name"] == "btaa-geo-api-cli"
    assert search["client_channel"] == "cli"
