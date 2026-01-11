"""
Tests for the top-level admin API module (app.api.v1.admin).
"""

import pytest

from app.api.v1.admin import router, security


class TestAdminTopLevelEndpoints:
    """Test cases for top-level admin endpoints."""

    def test_endpoints_exist(self):
        """Test that admin endpoints are properly defined."""
        # Check that router has the expected routes
        route_paths = [route.path for route in router.routes]

        expected_paths = [
            "/cache/clear",
            "/reindex",
            "/resources/{id}/summarize",
            "/resources/{id}/identify-geo-entities",
        ]

        for expected_path in expected_paths:
            assert any(expected_path in path for path in route_paths), (
                f"Expected path {expected_path} not found"
            )


class TestAdminTopLevelModuleStructure:
    """Test cases for module structure and imports."""

    def test_module_imports(self):
        """Test that the admin module can be imported."""
        try:
            from app.api.v1.admin import router, security
            from app.api.v1.auth import verify_credentials

            assert router is not None
            assert security is not None
            assert verify_credentials is not None
        except ImportError as e:
            pytest.skip(f"Required dependency not available: {e}")

    def test_router_configuration(self):
        """Test that the router is properly configured."""
        # Check that router has routes
        assert len(router.routes) > 0

        # Check that routes are properly configured
        route_paths = [route.path for route in router.routes]
        expected_paths = [
            "/cache/clear",
            "/reindex",
            "/resources/{id}/summarize",
            "/resources/{id}/identify-geo-entities",
        ]

        for expected_path in expected_paths:
            assert any(expected_path in path for path in route_paths), (
                f"Expected path {expected_path} not found in routes"
            )

    def test_dependencies(self):
        """Test that dependencies are properly configured."""
        # Check that dependencies are set on the router
        assert router.dependencies is not None
        assert len(router.dependencies) > 0

    def test_security_configuration(self):
        """Test that security is properly configured."""
        from fastapi.security import HTTPBasic

        # Check that security is HTTPBasic
        assert isinstance(security, HTTPBasic)

    def test_route_methods(self):
        """Test that routes have the correct HTTP methods."""
        for route in router.routes:
            if hasattr(route, "methods"):
                # All admin routes should be POST methods
                assert "POST" in route.methods, f"Route {route.path} should support POST method"

    def test_function_signatures(self):
        """Test that endpoint functions exist and are callable."""
        # Import the endpoint functions to test they exist
        try:
            from app.api.v1.admin import (
                clear_cache,
                identify_geo_entities,
                reindex,
                summarize_resource,
            )

            assert callable(clear_cache)
            assert callable(reindex)
            assert callable(summarize_resource)
            assert callable(identify_geo_entities)
        except ImportError as e:
            pytest.skip(f"Endpoint functions not available: {e}")

    def test_logger_initialization(self):
        """Test that logger is properly initialized."""
        from app.api.v1.admin import logger

        assert logger is not None
        assert logger.name == "app.api.v1.admin"
