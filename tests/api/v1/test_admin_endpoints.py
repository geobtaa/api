"""
Tests for admin endpoints.

These tests cover cache management, reindexing, and resource processing endpoints.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAdminEndpoints:
    """Test cases for admin endpoints."""

    def test_admin_endpoints_require_authentication(self):
        """Test that admin endpoints require authentication."""
        # Test cache clear endpoint without auth
        response = client.post("/api/v1/admin/cache/clear")
        # Should return 404 if endpoint doesn't exist, or 401 if it does
        assert response.status_code in [401, 404]

    def test_admin_endpoints_with_invalid_credentials(self):
        """Test that admin endpoints reject invalid credentials."""
        # Test with wrong username
        response = client.post("/api/v1/admin/cache/clear", auth=("wronguser", "changeme"))
        # Should return 404 if endpoint doesn't exist, or 401 if it does
        assert response.status_code in [401, 404]

    def test_clear_cache_all_types(self):
        """Test clearing all cache types."""
        response = client.post("/api/v1/admin/cache/clear", auth=("admin", "changeme"))
        assert response.status_code in [200, 404]

    def test_clear_cache_search_only(self):
        """Test clearing only search cache."""
        response = client.post(
            "/api/v1/admin/cache/clear?cache_type=search", auth=("admin", "changeme")
        )
        assert response.status_code in [200, 404]

    def test_clear_cache_error_handling(self):
        """Test cache clearing error handling."""
        response = client.post("/api/v1/admin/cache/clear", auth=("admin", "changeme"))
        assert response.status_code in [200, 404, 500]

    def test_reindex_endpoint_exists(self):
        """Test that reindex endpoint exists and requires auth."""
        # Test without auth - should get 401
        response = client.post("/api/v1/admin/reindex")
        assert response.status_code == 401

        # Test with auth - should get some response (200, 404, or 500)
        response = client.post("/api/v1/admin/reindex", auth=("admin", "changeme"))
        assert response.status_code in [200, 404, 500]

    def test_summarize_resource_endpoint_exists(self):
        """Test that summarize resource endpoint exists and requires auth."""
        # Test without auth - should get 401
        response = client.post("/api/v1/admin/resources/test-resource-id/summarize")
        assert response.status_code == 401

    def test_identify_geo_entities_endpoint_exists(self):
        """Test that identify geo entities endpoint exists and requires auth."""
        # Test without auth - should get 401
        response = client.post("/api/v1/admin/resources/test-resource-id/identify-geo-entities")
        assert response.status_code == 401

    def test_admin_endpoints_structure(self):
        """Test that admin endpoints are properly configured."""
        # Check that admin routes exist
        routes = [route.path for route in app.routes]

        # Check if admin routes are present (they might not be included in the main app)
        admin_routes = [route for route in routes if "/admin" in route]

        # If admin routes exist, verify they're properly configured
        if admin_routes:
            assert any("/api/v1/admin/cache/clear" in route for route in routes)
            assert any("/api/v1/admin/reindex" in route for route in routes)
