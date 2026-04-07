"""
Tests for the API key service.
"""

import hashlib
import uuid

import pytest

from app.services.api_key_service import (
    API_KEY_HASH_ITERATIONS,
    APIKeyService,
)


@pytest.mark.unit
class TestAPIKeyService:
    """Test cases for APIKeyService."""

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
