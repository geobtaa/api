"""
Tests for the admin API endpoints.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.admin import router

# Create test app
app = FastAPI()
app.include_router(router, prefix="/admin")

# Test client
client = TestClient(app)


class TestAdminEndpoints:
    """Test cases for admin endpoints."""

    def test_clear_cache_unauthorized(self):
        """Test cache clearing without proper authentication."""
        response = client.post("/admin/cache/clear", auth=("wrong", "credentials"))

        assert response.status_code == 401

    def test_clear_cache_no_auth(self):
        """Test cache clearing without authentication."""
        response = client.post("/admin/cache/clear")

        assert response.status_code == 401


class TestReindexEndpoint:
    """Test cases for reindex endpoint."""

    def test_reindex_unauthorized(self):
        """Test reindexing without proper authentication."""
        response = client.post("/admin/reindex", auth=("wrong", "credentials"))

        assert response.status_code == 401

    def test_reindex_no_auth(self):
        """Test reindexing without authentication."""
        response = client.post("/admin/reindex")

        assert response.status_code == 401


class TestProcessResourceEndpoint:
    """Test cases for process resource endpoint."""

    def test_summarize_resource_unauthorized(self):
        """Test resource summarization without proper authentication."""
        response = client.post("/admin/resources/test-id/summarize", auth=("wrong", "credentials"))

        assert response.status_code == 401

    def test_summarize_resource_no_auth(self):
        """Test resource summarization without authentication."""
        response = client.post("/admin/resources/test-id/summarize")

        assert response.status_code == 401


class TestProcessAllResourcesEndpoint:
    """Test cases for process all resources endpoint - this endpoint doesn't exist."""

    def test_nonexistent_endpoint(self):
        """Test that non-existent endpoints return 404."""
        response = client.post("/admin/process/all", auth=("admin", "changeme"))

        # Should return 404 since this endpoint doesn't exist
        assert response.status_code == 404

    def test_nonexistent_endpoint_unauthorized(self):
        """Test that non-existent endpoints still return 404 even without auth."""
        response = client.post("/admin/process/all", auth=("wrong", "credentials"))

        assert response.status_code == 404


class TestAdminAuthentication:
    """Test cases for admin authentication."""

    def test_all_endpoints_require_auth(self):
        """Test that all admin endpoints require authentication."""
        endpoints = ["/admin/cache/clear", "/admin/reindex", "/admin/resources/test-id/summarize"]

        for endpoint in endpoints:
            response = client.post(endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"

    def test_wrong_credentials(self):
        """Test that wrong credentials are rejected."""
        endpoints = ["/admin/cache/clear", "/admin/reindex", "/admin/resources/test-id/summarize"]

        for endpoint in endpoints:
            response = client.post(endpoint, auth=("wrong", "credentials"))
            assert response.status_code == 401, (
                f"Endpoint {endpoint} should reject wrong credentials"
            )

    def test_correct_credentials(self):
        """Test that correct credentials are accepted."""
        response = client.post("/admin/cache/clear", auth=("admin", "changeme"))

        # Should not be 401 (unauthorized) - could be 200 or 500 depending on Redis
        assert response.status_code != 401


class TestAdminResponseFormat:
    """Test cases for admin response format."""

    def test_unauthorized_response_format(self):
        """Test that unauthorized responses have correct format."""
        response = client.post("/admin/cache/clear")

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
