from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from starlette.datastructures import QueryParams

from app.services.api_usage_log_service import APIUsageLogService


def _build_request():
    return SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/search"),
        method="GET",
        headers={
            "User-Agent": "TestAgent/1.0",
            "Referer": "https://geo.btaa.org/search?q=maps",
            "X-Visit-Token": "visit-123",
            "X-Forwarded-For": "203.0.113.10, 10.0.0.2",
            "Origin": "https://geo.btaa.org",
            "X-BTAA-Client-Name": "geoportal-web",
            "X-BTAA-Client-Version": "test-build",
            "X-BTAA-Client-Channel": "browser",
            "X-BTAA-Client-Instance": "dev-local",
        },
        query_params=QueryParams("q=maps&utm_source=geoportal&utm_campaign=spring-launch"),
        client=SimpleNamespace(host="127.0.0.1"),
    )


@pytest.mark.asyncio
async def test_log_request_queues_celery_payload(monkeypatch):
    service = APIUsageLogService()
    request = _build_request()

    monkeypatch.setenv("DISABLE_API_USAGE_LOG", "false")
    monkeypatch.setenv("APP_ENV", "development")

    with patch("app.services.api_usage_log_service.write_api_usage_log.delay") as mock_delay:
        await service.log_request(
            request,
            tier_id=6,
            api_key_id=42,
            response_time_ms=87,
            status_code=200,
        )

    mock_delay.assert_called_once()
    payload = mock_delay.call_args.args[0]
    assert payload["tier_id"] == 6
    assert payload["api_key_id"] == 42
    assert payload["endpoint"] == "/api/v1/search"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["response_time_ms"] == 87
    assert payload["ip_address"] == "203.0.113.10"
    assert payload["visit_token"] == "visit-123"
    assert payload["referring_domain"] == "geo.btaa.org"
    assert payload["utm_source"] == "geoportal"
    assert payload["utm_campaign"] == "spring-launch"
    assert payload["properties"]["query_params"] == {"q": "maps"}
    assert payload["properties"]["origin"] == "https://geo.btaa.org"
    assert payload["client_name"] == "geoportal-web"
    assert payload["client_version"] == "test-build"
    assert payload["client_channel"] == "browser"
    assert payload["client_instance"] == "dev-local"
    assert payload["source_host"] == "geo.btaa.org"
    assert (
        payload["partition_month"]
        == datetime.fromisoformat(payload["requested_at"]).date().replace(day=1).isoformat()
    )
    assert isinstance(datetime.fromisoformat(payload["requested_at"]), datetime)


@pytest.mark.asyncio
async def test_log_request_skips_when_disabled(monkeypatch):
    service = APIUsageLogService()

    monkeypatch.setenv("DISABLE_API_USAGE_LOG", "true")
    monkeypatch.setenv("APP_ENV", "development")

    with patch("app.services.api_usage_log_service.write_api_usage_log.delay") as mock_delay:
        await service.log_request(_build_request(), tier_id=6)

    mock_delay.assert_not_called()


@pytest.mark.asyncio
async def test_log_request_swallows_queue_errors(monkeypatch):
    service = APIUsageLogService()

    monkeypatch.setenv("DISABLE_API_USAGE_LOG", "false")
    monkeypatch.setenv("APP_ENV", "development")

    with patch(
        "app.services.api_usage_log_service.write_api_usage_log.delay",
        side_effect=RuntimeError("redis down"),
    ):
        await service.log_request(_build_request(), tier_id=6)
