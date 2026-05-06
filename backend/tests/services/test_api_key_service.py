"""
Tests for the API key service.
"""

import hashlib
import uuid

import pytest

from app.services import api_key_service as api_key_service_module
from app.services.api_key_service import (
    API_KEY_HASH_ITERATIONS,
    APIKeyService,
)


@pytest.mark.unit
class TestAPIKeyService:
    """Test cases for APIKeyService."""

    @pytest.fixture(autouse=True)
    def clear_api_key_cache(self):
        """Keep process-local cache state isolated between tests."""
        APIKeyService.clear_cache()
        yield
        APIKeyService.clear_cache()

    @pytest.fixture
    def api_key_service(self):
        """Create an APIKeyService instance."""
        return APIKeyService()

    def test_generate_api_key(self, api_key_service):
        """Test API key generation."""
        key = api_key_service.generate_api_key()

        # Should be a valid UUID
        uuid.UUID(key)  # Will raise ValueError if not valid UUID
        assert len(key) == 36  # UUID v4 format

    def test_hash_api_key(self, api_key_service, monkeypatch):
        """Test API key hashing."""
        monkeypatch.setenv("API_KEY_HASH_SECRET", "test-hash-secret")
        key = "test-api-key-123"
        key_hash = api_key_service.hash_api_key(key)

        expected_hash = hashlib.pbkdf2_hmac(
            "sha256",
            key.encode("utf-8"),
            b"test-hash-secret",
            API_KEY_HASH_ITERATIONS,
            dklen=32,
        ).hex()

        # Should be a deterministic 64-character hex digest
        assert len(key_hash) == 64
        assert key_hash == expected_hash

    def test_hash_api_key_consistency(self, api_key_service):
        """Test that hashing the same key produces the same hash."""
        key = "test-api-key-123"
        hash1 = api_key_service.hash_api_key(key)
        hash2 = api_key_service.hash_api_key(key)

        assert hash1 == hash2

    def test_hash_api_key_different_keys(self, api_key_service):
        """Test that different keys produce different hashes."""
        key1 = "test-api-key-123"
        key2 = "test-api-key-456"
        hash1 = api_key_service.hash_api_key(key1)
        hash2 = api_key_service.hash_api_key(key2)

        assert hash1 != hash2

    def test_cache_lookup_key_does_not_store_raw_key(self, api_key_service):
        """Cache keys should not retain the plaintext API key."""
        lookup_key = api_key_service._cache_lookup_key("secret-api-key")

        assert "secret-api-key" not in lookup_key
        assert lookup_key == api_key_service.legacy_hash_api_key("secret-api-key")

    def test_cached_tier_returns_copy_and_expires(self, api_key_service, monkeypatch):
        """Cached tier data should be short-lived and isolated from caller mutation."""
        now = 1000.0
        monkeypatch.setattr(api_key_service_module, "API_KEY_TIER_CACHE_TTL_SECONDS", 60)
        monkeypatch.setattr(api_key_service_module.time, "monotonic", lambda: now)

        api_key_service._set_cached_tier("cache-key", {"tier_id": 1, "tier_name": "btaa"})

        cached_tier = api_key_service._get_cached_tier("cache-key", None)
        cached_tier["tier_id"] = 999

        assert api_key_service._get_cached_tier("cache-key", None)["tier_id"] == 1

        now = 1061.0

        assert api_key_service._get_cached_tier("cache-key", None) is None

    def test_cached_tier_still_enforces_allowed_ips(self, api_key_service, monkeypatch):
        """Cache hits must respect IP allowlists from the cached database row."""
        monkeypatch.setattr(api_key_service_module, "API_KEY_TIER_CACHE_TTL_SECONDS", 60)
        monkeypatch.setattr(api_key_service_module.time, "monotonic", lambda: 1000.0)

        api_key_service._set_cached_tier(
            "cache-key",
            {
                "tier_id": 1,
                "tier_name": "btaa",
                "allowed_ips": ["192.0.2.10"],
            },
        )

        assert api_key_service._get_cached_tier("cache-key", "192.0.2.10") is not None
        assert api_key_service._get_cached_tier("cache-key", "198.51.100.10") is None

    def test_cached_anonymous_tier_returns_copy(self, api_key_service, monkeypatch):
        """Anonymous tier lookups should be cached without exposing shared state."""
        now = 2000.0
        monkeypatch.setattr(api_key_service_module, "API_KEY_TIER_CACHE_TTL_SECONDS", 60)
        monkeypatch.setattr(api_key_service_module.time, "monotonic", lambda: now)

        api_key_service._set_cached_anonymous_tier(
            {
                "tier_id": 6,
                "tier_name": "anonymous",
                "display_name": "Anonymous",
                "requests_per_minute": 10,
            }
        )

        cached_tier = api_key_service._get_cached_anonymous_tier()
        cached_tier["requests_per_minute"] = 999

        assert api_key_service._get_cached_anonymous_tier()["requests_per_minute"] == 10

    def test_last_used_update_is_throttled(self, api_key_service, monkeypatch):
        """Repeated keyed requests should not force last_used_at writes every time."""
        now = 3000.0
        monkeypatch.setattr(
            api_key_service_module,
            "API_KEY_LAST_USED_UPDATE_INTERVAL_SECONDS",
            60,
        )
        monkeypatch.setattr(api_key_service_module.time, "monotonic", lambda: now)

        assert api_key_service._last_used_update_due(42) is True

        api_key_service._remember_last_used_update(42)

        assert api_key_service._last_used_update_due(42) is False

        now = 3061.0

        assert api_key_service._last_used_update_due(42) is True
