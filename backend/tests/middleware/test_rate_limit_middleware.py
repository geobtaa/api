"""
Tests for the rate limit middleware.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from app.middleware.rate_limit_middleware import (
    DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE,
    RateLimitMiddleware,
    _is_immutable_asset_route,
)


class TestRateLimitMiddleware:
    """Test cases for RateLimitMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Create a RateLimitMiddleware instance."""
        app = MagicMock()
        return RateLimitMiddleware(app)

    def test_extract_api_key_from_header(self, middleware):
        """Test extracting API key from X-API-Key header."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key, default=None: "test-api-key" if key == "X-API-Key" else default
        )
        request.query_params.get = MagicMock(return_value=None)

        api_key = middleware._extract_api_key(request)

        assert api_key == "test-api-key"

    def test_extract_api_key_from_bearer(self, middleware):
        """Test extracting API key from Authorization Bearer header."""
        request = MagicMock(spec=Request)

        # Helper function to keep line length within limits
        def _get_header(key, default=None):
            if key == "Authorization":
                return "Bearer test-api-key"
            return default

        request.headers.get = MagicMock(side_effect=_get_header)
        request.query_params.get = MagicMock(return_value=None)

        api_key = middleware._extract_api_key(request)

        assert api_key == "test-api-key"

    def test_extract_api_key_from_query_param(self, middleware):
        """Test extracting API key from query parameter."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value="test-api-key")

        api_key = middleware._extract_api_key(request)

        assert api_key == "test-api-key"

    def test_extract_api_key_none(self, middleware):
        """Test extracting API key when none provided."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value=None)

        api_key = middleware._extract_api_key(request)

        assert api_key is None

    def test_get_identifier_with_api_key(self, middleware):
        """Test getting identifier when API key is provided."""
        request = MagicMock(spec=Request)
        api_key = "test-api-key"
        tier_info = {"key_hash": "abc123hash"}

        identifier = middleware._get_identifier(request, api_key, tier_info)

        assert identifier == "abc123hash"

    def test_get_identifier_anonymous_with_forwarded_for(self, middleware):
        """Test getting identifier for anonymous request with X-Forwarded-For."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value="192.168.1.1, 10.0.0.1")
        request.client = None
        tier_info = {}

        identifier = middleware._get_identifier(request, None, tier_info)

        assert identifier == "192.168.1.1"

    def test_get_identifier_anonymous_with_client_ip(self, middleware):
        """Test getting identifier for anonymous request with client IP."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        tier_info = {}

        identifier = middleware._get_identifier(request, None, tier_info)

        assert identifier == "192.168.1.1"

    def test_extract_ip_address_from_forwarded_for(self, middleware):
        """Test extracting IP address from X-Forwarded-For header."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key, default=None: "192.168.1.1, 10.0.0.1"
            if key == "X-Forwarded-For"
            else default
        )
        request.client = None

        ip_address = middleware._extract_ip_address(request)

        assert ip_address == "192.168.1.1"

    def test_extract_ip_address_from_client(self, middleware):
        """Test extracting IP address from client host."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.2"

        ip_address = middleware._extract_ip_address(request)

        assert ip_address == "192.168.1.2"

    def test_extract_ip_address_none(self, middleware):
        """Test extracting IP address when none available."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.client = None

        ip_address = middleware._extract_ip_address(request)

        assert ip_address is None

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            (
                "/api/v1/thumbnails/"
                "e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639",
                True,
            ),
            (
                "/api/v1/thumbnails/"
                "E7810CCA426F65FA9E5E25124CA1B213B6C54DEEC0901C88805558FAA7E25639",
                True,
            ),
            ("/api/v1/thumbnails/placeholder", False),
            ("/api/v1/thumbnails/stanford-fc944xn1421", False),
            ("/api/v1/resources/stanford-fc944xn1421/thumbnail", False),
        ],
    )
    def test_is_immutable_asset_route(self, path, expected):
        """Only content-hash thumbnail assets should bypass the limiter."""
        assert _is_immutable_asset_route(path) is expected

    @pytest.mark.asyncio
    async def test_get_tier_info_with_ip_whitelist_allowed(self, middleware):
        """Test tier info retrieval when IP is in whitelist."""
        request_ip = "192.168.1.1"
        api_key = "test-key"

        # Mock validate_api_key to return tier info (IP is whitelisted)
        tier_info = {
            "tier_id": 1,
            "tier_name": "general_registered",
            "display_name": "General Registered",
            "requests_per_minute": 100,
            "api_key_id": 1,
            "key_hash": "test-hash",
        }

        middleware.api_key_service.validate_api_key = AsyncMock(return_value=tier_info)

        result = await middleware._get_tier_info(api_key, request_ip)

        assert result == tier_info
        middleware.api_key_service.validate_api_key.assert_called_once_with(api_key, request_ip)

    @pytest.mark.asyncio
    async def test_get_tier_info_with_ip_whitelist_rejected(self, middleware):
        """Test tier info retrieval when IP is not in whitelist (falls back to anonymous)."""
        request_ip = "192.168.1.999"  # Not whitelisted
        api_key = "test-key"

        # Mock validate_api_key to return None (IP restriction failed)
        middleware.api_key_service.validate_api_key = AsyncMock(return_value=None)
        anonymous_tier = {
            "tier_id": 6,
            "tier_name": "anonymous",
            "display_name": "Anonymous",
            "requests_per_minute": 10,
        }
        middleware.api_key_service.get_anonymous_tier = AsyncMock(return_value=anonymous_tier)

        result = await middleware._get_tier_info(api_key, request_ip)

        assert result == anonymous_tier
        middleware.api_key_service.validate_api_key.assert_called_once_with(api_key, request_ip)
        middleware.api_key_service.get_anonymous_tier.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_disabled(self, middleware):
        """Requests should still log even when throttling is disabled."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/v1/search"
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        tier_info = {
            "tier_id": 6,
            "tier_name": "anonymous",
            "display_name": "Anonymous",
            "requests_per_minute": 10,
        }
        middleware.api_key_service.get_anonymous_tier = AsyncMock(return_value=tier_info)
        middleware.usage_log_service.log_request = AsyncMock()
        middleware.rate_limit_service.check_rate_limit = AsyncMock()

        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "false",
                "DISABLE_RATE_LIMIT_FOR_TESTS": "false",
            },
            clear=False,
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        middleware.rate_limit_service.check_rate_limit.assert_not_called()
        middleware.usage_log_service.log_request.assert_called_once()
        assert response is not None
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers

    @pytest.mark.asyncio
    async def test_dispatch_admin_endpoint_skipped(self, middleware):
        """Admin requests should bypass throttling but still log usage."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/v1/admin/cache/clear"
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        tier_info = {
            "tier_id": 6,
            "tier_name": "anonymous",
            "display_name": "Anonymous",
            "requests_per_minute": 10,
        }
        middleware.api_key_service.get_anonymous_tier = AsyncMock(return_value=tier_info)
        middleware.usage_log_service.log_request = AsyncMock()
        middleware.rate_limit_service.check_rate_limit = AsyncMock()
        call_next = AsyncMock(return_value=JSONResponse(content={}))

        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "DISABLE_RATE_LIMIT_FOR_TESTS": "false",
            },
            clear=False,
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        middleware.rate_limit_service.check_rate_limit.assert_not_called()
        middleware.usage_log_service.log_request.assert_called_once()
        assert response is not None

    @pytest.mark.asyncio
    async def test_dispatch_immutable_thumbnail_asset_skipped(self, middleware):
        """Immutable cached thumbnail assets should bypass throttling but still log."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = (
            "/api/v1/thumbnails/e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639"
        )
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        tier_info = {
            "tier_id": 6,
            "tier_name": "anonymous",
            "display_name": "Anonymous",
            "requests_per_minute": 10,
        }
        middleware.api_key_service.get_anonymous_tier = AsyncMock(return_value=tier_info)
        middleware.usage_log_service.log_request = AsyncMock()
        middleware.rate_limit_service.check_rate_limit = AsyncMock()
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "DISABLE_RATE_LIMIT_FOR_TESTS": "false",
            },
            clear=False,
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        middleware.rate_limit_service.check_rate_limit.assert_not_called()
        middleware.usage_log_service.log_request.assert_called_once()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_options_preflight_skipped_without_logging(self, middleware):
        """CORS preflights should not consume quota or create usage-log writes."""
        request = MagicMock(spec=Request)
        request.method = "OPTIONS"
        request.url = MagicMock()
        request.url.path = "/api/v1/search"
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        middleware.usage_log_service.log_request = AsyncMock()
        middleware.rate_limit_service.check_rate_limit = AsyncMock()
        middleware.api_key_service.get_anonymous_tier = AsyncMock()
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        middleware.api_key_service.get_anonymous_tier.assert_not_called()
        middleware.rate_limit_service.check_rate_limit.assert_not_called()
        middleware.usage_log_service.log_request.assert_not_called()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_analytics_uses_separate_ip_bucket(self, middleware):
        """Analytics events should not spend the normal anonymous/API-key quota."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/v1/analytics/events"
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        tier_info = {
            "tier_id": 6,
            "tier_name": "anonymous",
            "display_name": "Anonymous",
            "requests_per_minute": 10,
        }
        middleware.api_key_service.get_anonymous_tier = AsyncMock(return_value=tier_info)
        middleware.rate_limit_service.check_rate_limit = AsyncMock(
            return_value=(True, DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE - 1, 1234567890)
        )
        middleware.rate_limit_service.get_rate_limit_headers = AsyncMock(
            return_value={
                "X-RateLimit-Limit": str(DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE),
                "X-RateLimit-Remaining": str(DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE - 1),
                "X-RateLimit-Reset": "1234567890",
            }
        )
        middleware.usage_log_service.log_request = AsyncMock()
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=202))

        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "DISABLE_RATE_LIMIT_FOR_TESTS": "false",
            },
            clear=False,
        ):
            response = await middleware.dispatch(request, call_next)

        middleware.rate_limit_service.check_rate_limit.assert_called_once_with(
            "analytics_events",
            "ip:192.168.1.1",
            DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE,
        )
        call_next.assert_called_once_with(request)
        middleware.usage_log_service.log_request.assert_called_once()
        assert response.status_code == 202
        assert response.headers["X-RateLimit-Limit"] == str(
            DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE
        )

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_exceeded(self, middleware):
        """Test that middleware returns 429 when rate limit exceeded."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/v1/search"
        request.headers.get = MagicMock(return_value=None)
        request.query_params.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        # Mock tier info (anonymous)
        tier_info = {
            "tier_name": "anonymous",
            "requests_per_minute": 10,
        }

        # Mock API key service
        middleware.api_key_service.get_anonymous_tier = AsyncMock(return_value=tier_info)

        # Mock rate limit service to return limit exceeded
        middleware.rate_limit_service.check_rate_limit = AsyncMock(
            return_value=(False, 0, 1234567890)
        )

        # Simulate downstream handler returning a normal response
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        # Force rate limiting on and bypass flag off for this test
        with patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "true",
                "DISABLE_RATE_LIMIT_FOR_TESTS": "false",
            },
            clear=False,
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 429
        assert "Rate limit exceeded" in str(response.body)
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_unlimited_tier(self, middleware):
        """Test that middleware allows unlimited tier requests."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/v1/search"
        request.headers.get = MagicMock(return_value="test-api-key")
        request.query_params.get = MagicMock(return_value=None)

        # Mock tier info (unlimited)
        tier_info = {
            "tier_name": "btaa_primary",
            "requests_per_minute": None,  # Unlimited
            "key_hash": "test_hash",
        }

        # Mock API key service
        middleware.api_key_service.validate_api_key = AsyncMock(return_value=tier_info)

        # Mock rate limit service
        middleware.rate_limit_service.get_rate_limit_headers = AsyncMock(
            return_value={
                "X-RateLimit-Limit": "unlimited",
                "X-RateLimit-Remaining": "unlimited",
                "X-RateLimit-Reset": "1234567890",
            }
        )

        call_next = AsyncMock(return_value=JSONResponse(content={}))

        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert response.status_code == 200
