from __future__ import annotations

from unittest.mock import MagicMock

from app.services.api_usage_log_service import APIUsageLogService


def test_cli_headers_and_api_key_id_are_preserved_in_usage_log_payload():
    request = MagicMock()
    request.url.path = "/api/v1/search"
    request.method = "GET"
    request.client.host = "192.0.2.10"
    request.query_params = {"q": "water"}
    request.headers = {
        "User-Agent": "BTAA-Geo-API-CLI/0.1.0",
        "X-BTAA-Client-Name": "btaa-geo-api-cli",
        "X-BTAA-Client-Version": "0.1.0",
        "X-BTAA-Client-Channel": "cli",
        "X-BTAA-Client-Instance": "instance-1",
    }

    payload = APIUsageLogService()._build_log_entry(
        request,
        tier_id=7,
        api_key_id=42,
        response_time_ms=123,
        status_code=200,
    )

    assert payload["api_key_id"] == 42
    assert payload["tier_id"] == 7
    assert payload["client_name"] == "btaa-geo-api-cli"
    assert payload["client_channel"] == "cli"
    assert payload["client_instance"] == "instance-1"
    assert payload["user_agent"] == "BTAA-Geo-API-CLI/0.1.0"
    assert payload["properties"]["query_params"] == {"q": "water"}
