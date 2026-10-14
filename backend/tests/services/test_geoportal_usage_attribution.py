from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.services.analytics_reporting.storage import dimensions
from app.services.api_key_service import APIKeyService
from app.services.api_usage_log_service import APIUsageLogService
from app.tasks.api_usage_enrichment import _prepare_log_entry, _resolve_log_tier


def request(headers=()):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/search",
            "query_string": b"q=maps&page=2",
            "headers": list(headers),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
        }
    )


@pytest.mark.asyncio
async def test_unlimited_key_queues_success_and_error_responses(monkeypatch):
    monkeypatch.setenv("BTAA_GEOSPATIAL_API_KEY", "test-only-geoportal-key")
    monkeypatch.setenv("DISABLE_API_USAGE_LOG", "false")
    monkeypatch.setenv("APP_ENV", "development")
    tier = APIKeyService._configured_server_key_tier("test-only-geoportal-key")
    assert tier["requests_per_minute"] is None
    middleware = RateLimitMiddleware(MagicMock())
    middleware._get_tier_info = AsyncMock(return_value=tier)
    middleware.rate_limit_service.get_rate_limit_headers = AsyncMock(return_value={})
    middleware.rate_limit_service.check_rate_limit = AsyncMock()
    with patch(
        "app.middleware.rate_limit_middleware._bypass_rate_limit_for_tests", return_value=False
    ):
        with patch("app.services.api_usage_log_service.write_api_usage_log.delay") as queue:
            for status in (200, 500):
                await middleware.dispatch(
                    request([(b"x-api-key", b"test-only-geoportal-key")]),
                    AsyncMock(return_value=Response(status_code=status)),
                )
                payload = queue.call_args.args[0]
                assert payload["status_code"] == status
                assert payload["client_name"] == "geoportal-ssr"
                assert payload["properties"]["authenticated_identity"] == "geoportal-unlimited"
                assert "test-only-geoportal-key" not in str(payload)
            assert queue.call_count == 2
    middleware.rate_limit_service.check_rate_limit.assert_not_called()


def test_verified_identity_survives_storage_and_preserves_browser_channel():
    payload = APIUsageLogService()._build_log_entry(
        request(
            [(b"x-btaa-client-name", b"geoportal-web"), (b"x-btaa-client-channel", b"browser")]
        ),
        tier_id=None,
        authenticated_identity="geoportal-unlimited",
        verified_key_hashes=("a" * 64, "b" * 64),
    )
    prepared = _prepare_log_entry(payload)
    conn = MagicMock()
    conn.execute.return_value.scalar_one.return_value = 23
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": 129,
        "name": "Production frontend BFF",
    }
    _resolve_log_tier(conn, prepared)
    assert prepared["tier_id"] == 23
    result = dimensions("analytics_api_usage_logs", prepared)
    assert result["apiKey"] == "Key 129"
    assert prepared["api_key_id"] == 129
    assert "_verified_key_hashes" not in prepared
    assert "a" * 64 not in str(prepared)
    assert result["client"] == "geoportal-web"
    assert result["channel"] == "browser"


def test_caller_label_cannot_claim_verified_identity():
    payload = APIUsageLogService()._build_log_entry(
        request(
            [
                (b"x-btaa-client-name", b"geoportal-ssr"),
                (b"x-authenticated-identity", b"geoportal-unlimited"),
            ]
        ),
        tier_id=1,
    )
    assert dimensions("analytics_api_usage_logs", payload)["apiKey"] == "Anonymous"
    conn = MagicMock()
    _resolve_log_tier(conn, payload)
    conn.execute.assert_not_called()
    payload["tier_id"] = None
    with pytest.raises(ValueError):
        _resolve_log_tier(conn, payload)


def test_rotated_key_resolves_using_captured_hashes_not_current_environment(monkeypatch):
    monkeypatch.setenv("BTAA_GEOSPATIAL_API_KEY", "new-key-after-rotation")
    entry = _prepare_log_entry(
        APIUsageLogService()._build_log_entry(
            request(),
            tier_id=None,
            authenticated_identity="geoportal-unlimited",
            verified_key_hashes=("old-current-hash", "old-legacy-hash"),
        )
    )
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"id": 129, "name": "BFF"}
    conn.execute.return_value.scalar_one.return_value = 1
    _resolve_log_tier(conn, entry)
    assert conn.execute.call_args_list[0].args[1] == {
        "current": "old-current-hash",
        "legacy": "old-legacy-hash",
    }
    assert entry["api_key_id"] == 129


def test_missing_registry_record_is_known_key_use_not_anonymous():
    entry = _prepare_log_entry(
        APIUsageLogService()._build_log_entry(
            request(),
            tier_id=None,
            authenticated_identity="geoportal-unlimited",
            verified_key_hashes=("a" * 64, "b" * 64),
        )
    )
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    conn.execute.return_value.scalar_one.return_value = 1
    _resolve_log_tier(conn, entry)
    assert entry["api_key_id"] is None
    assert entry["properties"]["key_registry_status"] == "unmatched"
    assert (
        dimensions("analytics_api_usage_logs", entry)["apiKey"]
        == "Geoportal unlimited (registry unmatched)"
    )
    assert "_verified_key_hashes" not in entry
