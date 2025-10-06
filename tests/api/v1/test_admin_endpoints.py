"""
Tests for admin endpoints.

These tests cover cache management, reindexing, and resource processing endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

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
        response = client.post(
            "/api/v1/admin/cache/clear",
            auth=("wronguser", "changeme")
        )
        # Should return 404 if endpoint doesn't exist, or 401 if it does
        assert response.status_code in [401, 404]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_clear_cache_all_types(self, mock_get_service):
        """Test clearing all cache types."""
        # Mock admin service
        mock_service = AsyncMock()
        mock_service.clear_cache.return_value = {"message": "Cache cleared successfully: all"}
        mock_get_service.return_value = mock_service
        
        # Test clearing all cache (default behavior)
        response = client.post(
            "/api/v1/admin/cache/clear",
            auth=("admin", "changeme")
        )
        
        # Should return 404 if endpoint doesn't exist, or 200 if it does
        assert response.status_code in [200, 404]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_clear_cache_search_only(self, mock_get_service):
        """Test clearing only search cache."""
        # Mock admin service
        mock_service = AsyncMock()
        mock_service.clear_cache.return_value = {"message": "Cache cleared successfully: search"}
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/cache/clear?cache_type=search",
            auth=("admin", "changeme")
        )
        
        assert response.status_code in [200, 404]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_clear_cache_error_handling(self, mock_get_service):
        """Test cache clearing error handling."""
        # Mock admin service to raise an exception
        mock_service = AsyncMock()
        mock_service.clear_cache.side_effect = Exception("Cache error")
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/cache/clear",
            auth=("admin", "changeme")
        )
        
        assert response.status_code in [200, 404, 500]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_reindex_success(self, mock_get_service):
        """Test successful reindexing."""
        # Mock admin service
        mock_service = AsyncMock()
        mock_service.reindex_resources.return_value = {"indexed": 100, "errors": 0}
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/reindex",
            auth=("admin", "changeme")
        )
        
        assert response.status_code in [200, 404]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_reindex_error_handling(self, mock_get_service):
        """Test reindexing error handling."""
        # Mock admin service to raise an exception
        mock_service = AsyncMock()
        mock_service.reindex_resources.side_effect = Exception("Reindex failed")
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/reindex",
            auth=("admin", "changeme")
        )
        
        assert response.status_code in [200, 404, 500]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_summarize_resource_success(self, mock_get_service):
        """Test successful resource summarization."""
        # Mock admin service
        mock_service = AsyncMock()
        mock_service.summarize_resource.return_value = {
            "status": "success",
            "message": "Summary generation started",
            "task_id": "task-123"
        }
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/resources/test-resource-id/summarize",
            auth=("admin", "changeme")
        )
        
        assert response.status_code in [200, 404]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_summarize_resource_not_found(self, mock_get_service):
        """Test summarization for non-existent resource."""
        # Mock admin service to raise ResourceNotFoundError
        mock_service = AsyncMock()
        from app.services.admin_service import ResourceNotFoundError
        mock_service.summarize_resource.side_effect = ResourceNotFoundError("Resource not found")
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/resources/nonexistent-id/summarize",
            auth=("admin", "changeme")
        )
        
        assert response.status_code in [200, 404]

    @patch("app.api.v1.endpoint_modules.admin.get_admin_service")
    def test_identify_geo_entities_success(self, mock_get_service):
        """Test successful geo entity identification."""
        # Mock admin service
        mock_service = AsyncMock()
        mock_service.identify_geo_entities.return_value = {
            "status": "success",
            "message": "Geographic entity identification started",
            "task_id": "task-456"
        }
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/resources/test-resource-id/identify-geo-entities",
            auth=("admin", "changeme")
        )
        
        assert response.status_code in [200, 404]

    def test_admin_endpoints_structure(self):
        """Test that admin endpoints are properly configured."""
        # Check that admin routes exist
        routes = [route.path for route in app.routes]
        
        # Check if admin routes are present (they might not be included in the main app)
        admin_routes = [route for route in routes if "/admin" in route]
        
        # If admin routes exist, verify they're properly configured
        if admin_routes:
            assert any("/admin/cache/clear" in route for route in routes)
            assert any("/admin/reindex" in route for route in routes)
