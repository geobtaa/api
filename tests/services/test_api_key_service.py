"""
Tests for the API key service.
"""

import hashlib
import uuid

import pytest

from app.services.api_key_service import APIKeyService


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

    def test_hash_api_key(self, api_key_service):
        """Test API key hashing."""
        key = "test-api-key-123"
        key_hash = api_key_service.hash_api_key(key)

        # Should be SHA-256 hash (64 hex characters)
        assert len(key_hash) == 64
        assert key_hash == hashlib.sha256(key.encode()).hexdigest()

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
