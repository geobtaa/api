"""
Integration tests for admin API key and tier endpoints.
"""

import os
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from app.main import app
from db.migrations.initialize_api_tiers import initialize_api_tiers

# Configure admin credentials for testing
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "changeme")


@pytest.fixture
def admin_client() -> TestClient:
    """Test client using the main FastAPI app with all middleware and routes."""
    return TestClient(app)


@pytest.mark.integration
@pytest.mark.database
class TestAdminAPIKeysLifecycle:
    """End-to-end tests for API key lifecycle via admin endpoints."""

    def setup_method(self):
        # Seed service tiers in the test database (idempotent).
        # This must run in setup_method (not fixture) to ensure it happens
        # after database connection is established but before test runs.
        # Uses synchronous connection that commits, visible to all async sessions.
        initialize_api_tiers()
        self.auth = ("admin", "changeme")

    def test_list_tiers(self, admin_client: TestClient):
        """List service tiers to ensure the endpoint is wired."""
        response = admin_client.get("/api/v1/admin/api-tiers", auth=self.auth)
        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        assert isinstance(data["tiers"], list)
        # Should at least contain the anonymous tier seeded by initialize_api_tiers
        tier_names = {t["tier_name"] for t in data["tiers"]}
        assert "anonymous" in tier_names

    def test_api_key_full_lifecycle(self, admin_client: TestClient):
        """Create, list, update, and revoke an API key via admin endpoints."""
        # Ensure tiers exist (idempotent, safe to call multiple times)
        # This uses synchronous connection that commits immediately
        initialize_api_tiers()

        # Verify tier exists before creating key (helps debug if tier lookup fails)
        tiers_resp = admin_client.get("/api/v1/admin/api-tiers", auth=self.auth)
        assert tiers_resp.status_code == 200
        tiers_data = tiers_resp.json()
        tier_names = {t["tier_name"] for t in tiers_data["tiers"]}
        assert "anonymous" in tier_names, f"Anonymous tier not found. Available tiers: {tier_names}"

        # 1. Create key for anonymous tier (exists in seed data)
        create_payload = {"tier_name": "anonymous", "name": "test-key"}
        create_resp = admin_client.post(
            "/api/v1/admin/api-keys",
            json=create_payload,
            auth=self.auth,
        )
        # If 400, check the error message to debug
        if create_resp.status_code != 200:
            error_data = create_resp.json()
            # More detailed error message
            pytest.fail(
                f"API key creation failed with status {create_resp.status_code}: {error_data}"
            )
        assert create_resp.status_code == 200
        created: Dict = create_resp.json()
        assert "api_key" in created  # plaintext key shown once
        assert created["tier_name"] == "anonymous"
        key_id = created["key_id"]

        # 2. List keys and confirm our key is present
        list_resp = admin_client.get("/api/v1/admin/api-keys", auth=self.auth)
        assert list_resp.status_code == 200
        listed = list_resp.json()
        assert "keys" in listed
        key_ids = [k["id"] for k in listed["keys"]]
        assert key_id in key_ids

        # 3. Update key: change name and (redundantly) keep same tier
        update_payload = {
            "tier_name": "anonymous",
            "name": "test-key-updated",
            "is_active": True,
        }
        update_resp = admin_client.patch(
            f"/api/v1/admin/api-keys/{key_id}",
            json=update_payload,
            auth=self.auth,
        )
        assert update_resp.status_code == 200
        update_data = update_resp.json()
        assert "message" in update_data

        # 4. Revoke key
        revoke_resp = admin_client.delete(
            f"/api/v1/admin/api-keys/{key_id}",
            auth=self.auth,
        )
        assert revoke_resp.status_code == 200
        revoke_data = revoke_resp.json()
        assert "message" in revoke_data

    def test_create_api_key_with_ip_whitelist(self, admin_client: TestClient):
        """Test creating an API key with IP whitelist."""
        initialize_api_tiers()

        create_payload = {
            "tier_name": "anonymous",
            "name": "test-key-with-ips",
            "allowed_ips": ["192.168.1.1", "10.0.0.1"],
        }
        create_resp = admin_client.post(
            "/api/v1/admin/api-keys",
            json=create_payload,
            auth=self.auth,
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert "api_key" in created
        key_id = created["key_id"]

        # Verify IP whitelist is stored
        list_resp = admin_client.get("/api/v1/admin/api-keys", auth=self.auth)
        assert list_resp.status_code == 200
        listed = list_resp.json()
        key = next(k for k in listed["keys"] if k["id"] == key_id)
        assert key["allowed_ips"] == ["192.168.1.1", "10.0.0.1"]

    def test_create_api_key_with_invalid_ip(self, admin_client: TestClient):
        """Test creating an API key with invalid IP address."""
        initialize_api_tiers()

        create_payload = {
            "tier_name": "anonymous",
            "name": "test-key-invalid-ip",
            "allowed_ips": ["invalid-ip-address"],
        }
        create_resp = admin_client.post(
            "/api/v1/admin/api-keys",
            json=create_payload,
            auth=self.auth,
        )
        assert create_resp.status_code == 400
        assert "Invalid IP address" in create_resp.json()["detail"]

    def test_update_api_key_ip_whitelist(self, admin_client: TestClient):
        """Test updating an API key's IP whitelist."""
        initialize_api_tiers()

        # Create key without IP restriction
        create_payload = {"tier_name": "anonymous", "name": "test-key"}
        create_resp = admin_client.post(
            "/api/v1/admin/api-keys",
            json=create_payload,
            auth=self.auth,
        )
        assert create_resp.status_code == 200
        key_id = create_resp.json()["key_id"]

        # Update with IP whitelist
        update_payload = {"allowed_ips": ["192.168.1.100"]}
        update_resp = admin_client.patch(
            f"/api/v1/admin/api-keys/{key_id}",
            json=update_payload,
            auth=self.auth,
        )
        assert update_resp.status_code == 200

        # Verify IP whitelist is updated
        list_resp = admin_client.get("/api/v1/admin/api-keys", auth=self.auth)
        key = next(k for k in list_resp.json()["keys"] if k["id"] == key_id)
        assert key["allowed_ips"] == ["192.168.1.100"]
