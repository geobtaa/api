"""
End-to-end tests for rate limiting middleware behavior.
"""

from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.rate_limit_middleware import RateLimitMiddleware


def _create_app() -> FastAPI:
    """Create a minimal FastAPI app with the rate limit middleware enabled."""
    app = FastAPI()

    @app.get("/api/v1/test-endpoint")
    async def test_endpoint():
        return JSONResponse({"ok": True})

    @app.get("/api/v1/thumbnails/{image_hash}")
    async def thumbnail_asset(image_hash: str):
        return JSONResponse({"image_hash": image_hash})

    @app.get("/api/docs")
    async def docs():
        return JSONResponse({"docs": True})

    @app.get("/api/openapi.json")
    async def openapi_schema():
        return JSONResponse({"openapi": "3.1.0"})

    app.add_middleware(RateLimitMiddleware)
    return app


class DummyRateLimitService:
    """In-memory rate limit service for testing.

    Avoids the need for a real Redis instance while still exercising the
    middleware logic and header behavior.
    """

    def __init__(self):
        self._limits = {}

    async def check_rate_limit(
        self, tier_name: str, identifier: str, requests_per_minute: Optional[int]
    ):
        # Treat None as unlimited
        if requests_per_minute is None:
            return True, -1, 0

        key = (tier_name, identifier)
        count = self._limits.get(key, 0)
        if count >= requests_per_minute:
            return False, 0, 0

        self._limits[key] = count + 1
        remaining = requests_per_minute - self._limits[key]
        return True, remaining, 0

    async def get_rate_limit_headers(
        self,
        tier_name: str,
        identifier: str,
        requests_per_minute: Optional[int],
        remaining: Optional[int] = None,
        reset_time: Optional[int] = None,
    ) -> dict:
        if requests_per_minute is None:
            return {
                "X-RateLimit-Limit": "unlimited",
                "X-RateLimit-Remaining": "unlimited",
                "X-RateLimit-Reset": "0",
            }
        return {
            "X-RateLimit-Limit": str(requests_per_minute),
            "X-RateLimit-Remaining": str(remaining if remaining is not None else 0),
            "X-RateLimit-Reset": "0",
        }


@pytest.fixture(autouse=True)
def _set_rate_limit_env(monkeypatch):
    """Ensure rate limiting is enabled for these tests."""

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    # Ensure middleware is not bypassed for these integration tests
    monkeypatch.setenv("DISABLE_RATE_LIMIT_FOR_TESTS", "false")


@pytest.fixture
def rate_limited_client(monkeypatch):
    """Return a TestClient with middleware patched to use dummy services."""

    dummy_rate_limit = DummyRateLimitService()

    # Patch the rate limit service used inside the middleware
    monkeypatch.setattr(
        "app.middleware.rate_limit_middleware.RateLimitService",
        lambda: dummy_rate_limit,
    )

    # Force the middleware to use a simple, fixed tier
    async def fake_get_tier_info(self, api_key, request_ip):  # pragma: no cover - small shim
        return {
            "tier_id": 1,
            "tier_name": "anonymous",
            "display_name": "Anonymous",
            "requests_per_minute": 1,
        }

    monkeypatch.setattr(
        "app.middleware.rate_limit_middleware.RateLimitMiddleware._get_tier_info",
        fake_get_tier_info,
    )

    app = _create_app()
    return TestClient(app)


@pytest.fixture
def unlimited_key_client(monkeypatch):
    """Return a TestClient where one API key resolves to an unlimited tier."""

    dummy_rate_limit = DummyRateLimitService()

    monkeypatch.setattr(
        "app.middleware.rate_limit_middleware.RateLimitService",
        lambda: dummy_rate_limit,
    )

    async def fake_get_tier_info(self, api_key, request_ip):  # pragma: no cover - small shim
        if api_key == "frontend-server-key":
            return {
                "tier_id": None,
                "tier_name": "btaa_primary",
                "display_name": "BTAA Geoportal Frontend",
                "requests_per_minute": None,
                "api_key_id": None,
                "key_hash": "frontend-server-key-hash",
            }

        return {
            "tier_id": 1,
            "tier_name": "anonymous",
            "display_name": "Anonymous",
            "requests_per_minute": 1,
        }

    monkeypatch.setattr(
        "app.middleware.rate_limit_middleware.RateLimitMiddleware._get_tier_info",
        fake_get_tier_info,
    )

    app = _create_app()
    return TestClient(app)


class TestRateLimitMiddlewareIntegration:
    """Integration-style tests for rate limit middleware."""

    def test_rate_limit_headers_present(self, rate_limited_client):
        """Verify that responses include X-RateLimit headers."""

        response = rate_limited_client.get("/api/v1/test-endpoint")
        assert response.status_code == 200
        headers = response.headers
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    def test_rate_limit_exceeded_returns_429(self, rate_limited_client):
        """Verify that exceeding the limit returns HTTP 429."""

        # Limit is 1 request per minute for the anonymous tier configured above.
        first = rate_limited_client.get("/api/v1/test-endpoint")
        assert first.status_code == 200

        second = rate_limited_client.get("/api/v1/test-endpoint")
        assert second.status_code == 429
        body = second.json()
        assert body.get("error") == "Rate limit exceeded"

    def test_immutable_thumbnail_asset_bypasses_rate_limit(self, rate_limited_client):
        """Hash-addressed thumbnail assets should not consume the anonymous quota."""

        path = "/api/v1/thumbnails/e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639"
        first = rate_limited_client.get(path)
        second = rate_limited_client.get(path)

        assert first.status_code == 200
        assert second.status_code == 200
        assert "X-RateLimit-Limit" not in first.headers

    def test_documentation_routes_bypass_rate_limit(self, rate_limited_client):
        """Docs and OpenAPI schema should not consume the interactive API quota."""

        docs = rate_limited_client.get("/api/docs")
        schema = rate_limited_client.get("/api/openapi.json")
        first_api_call = rate_limited_client.get("/api/v1/test-endpoint")
        second_api_call = rate_limited_client.get("/api/v1/test-endpoint")

        assert docs.status_code == 200
        assert schema.status_code == 200
        assert "X-RateLimit-Limit" not in docs.headers
        assert "X-RateLimit-Limit" not in schema.headers
        assert first_api_call.status_code == 200
        assert second_api_call.status_code == 429

    def test_unlimited_key_never_returns_429(self, unlimited_key_client):
        """Unlimited tiers must bypass counters and report unlimited headers."""

        headers = {"X-API-Key": "frontend-server-key"}

        first = unlimited_key_client.get("/api/v1/test-endpoint", headers=headers)
        second = unlimited_key_client.get("/api/v1/test-endpoint", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.headers["X-RateLimit-Limit"] == "unlimited"
        assert second.headers["X-RateLimit-Remaining"] == "unlimited"
