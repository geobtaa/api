"""
Tests for the rate limit middleware.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from app.middleware.rate_limit_middleware import RateLimitMiddleware


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
        request.headers.get = MagicMock(
            side_effect=lambda key, default=None: "Bearer test-api-key" if key == "Authorization" else default
        )
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

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_disabled(self, middleware):
        """Test that middleware skips rate limiting when disabled."""
        with patch("app.middleware.rate_limit_middleware.RATE_LIMIT_ENABLED", False):
            request = MagicMock(spec=Request)
            call_next = AsyncMock(return_value=JSONResponse(content={}))

            response = await middleware.dispatch(request, call_next)

            call_next.assert_called_once_with(request)
            assert response is not None

    @pytest.mark.asyncio
    async def test_dispatch_admin_endpoint_skipped(self, middleware):
        """Test that middleware skips rate limiting for admin endpoints."""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/v1/admin/cache/clear"
        call_next = AsyncMock(return_value=JSONResponse(content={}))

        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert response is not None

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_exceeded(self, middleware):
        """Test that middleware returns 429 when rate limit exceeded."""
        request = MagicMock(spec=Request)
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

        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 429
        assert "Rate limit exceeded" in str(response.body)
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_unlimited_tier(self, middleware):
        """Test that middleware allows unlimited tier requests."""
        request = MagicMock(spec=Request)
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
