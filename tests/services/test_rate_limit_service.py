"""
Tests for the rate limit service.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.rate_limit_service import RateLimitService


class TestRateLimitService:
    """Test cases for RateLimitService."""

    @pytest.fixture
    def rate_limit_service(self):
        """Create a RateLimitService instance."""
        service = RateLimitService()
        return service

    @pytest.mark.asyncio
    async def test_check_rate_limit_unlimited_tier(self, rate_limit_service):
        """Test that unlimited tiers always allow requests."""
        allowed, remaining, reset_time = await rate_limit_service.check_rate_limit(
            "btaa_primary", "test_identifier", None
        )
        assert allowed is True
        assert remaining == -1  # -1 indicates unlimited
        assert reset_time >= int(time.time())  # Reset time should be current or future

    @pytest.mark.asyncio
    async def test_check_rate_limit_within_limit(self, rate_limit_service):
        """Test rate limiting when within limit."""
        with patch.object(rate_limit_service, "_redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="5")  # 5 requests so far
            mock_redis.incr = AsyncMock(return_value=6)
            mock_redis.expire = AsyncMock()

            allowed, remaining, reset_time = await rate_limit_service.check_rate_limit(
                "general_registered", "test_identifier", 100
            )

            assert allowed is True
            assert remaining == 94  # 100 - 5 - 1 (before increment)
            assert reset_time >= int(time.time())  # Reset time should be current or future
            mock_redis.incr.assert_called_once()
            mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limit_service):
        """Test rate limiting when limit exceeded."""
        with patch.object(rate_limit_service, "_redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="100")  # Already at limit
            mock_redis.incr = AsyncMock()
            mock_redis.expire = AsyncMock()

            allowed, remaining, reset_time = await rate_limit_service.check_rate_limit(
                "general_registered", "test_identifier", 100
            )

            assert allowed is False
            assert remaining == 0
            assert reset_time >= int(time.time())  # Reset time should be current or future
            # Should not increment when limit exceeded
            mock_redis.incr.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_redis(self, rate_limit_service):
        """Test that requests are allowed when Redis is unavailable."""
        rate_limit_service._redis_client = None

        allowed, remaining, reset_time = await rate_limit_service.check_rate_limit(
            "general_registered", "test_identifier", 100
        )

        assert allowed is True
        assert remaining == 100
        assert reset_time >= int(time.time())  # Reset time should be current or future

    @pytest.mark.asyncio
    async def test_get_rate_limit_headers_unlimited(self, rate_limit_service):
        """Test rate limit headers for unlimited tier."""
        headers = await rate_limit_service.get_rate_limit_headers(
            "btaa_primary", "test_identifier", None
        )

        assert headers["X-RateLimit-Limit"] == "unlimited"
        assert headers["X-RateLimit-Remaining"] == "unlimited"
        assert "X-RateLimit-Reset" in headers

    @pytest.mark.asyncio
    async def test_get_rate_limit_headers_with_values(self, rate_limit_service):
        """Test rate limit headers with provided remaining/reset_time."""
        headers = await rate_limit_service.get_rate_limit_headers(
            "general_registered", "test_identifier", 100, remaining=50, reset_time=1234567890
        )

        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "50"
        assert headers["X-RateLimit-Reset"] == "1234567890"

    @pytest.mark.asyncio
    async def test_get_current_rate_limit_status(self, rate_limit_service):
        """Test getting current rate limit status without incrementing."""
        with patch.object(rate_limit_service, "_redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="25")  # 25 requests so far

            remaining, reset_time = await rate_limit_service._get_current_rate_limit_status(
                "general_registered", "test_identifier", 100
            )

            assert remaining == 75  # 100 - 25
            assert reset_time > int(time.time())
            mock_redis.get.assert_called_once()
            # Should not increment
            assert not hasattr(mock_redis, "incr") or not mock_redis.incr.called
