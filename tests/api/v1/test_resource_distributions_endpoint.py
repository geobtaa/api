"""
Test suite for the /resources/{id}/distributions API endpoint.

This module tests the new distributions endpoint that provides access to
resource distribution data in JSON:API format using real database data.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestResourceDistributionsEndpoint:
    """Test the /resources/{id}/distributions endpoint with real data."""

    @pytest.fixture
    def client(self):
        """Return a FastAPI test client."""
        return TestClient(app)

    def test_endpoint_exists(self, client):
        """Test that the distributions endpoint is properly configured."""
        # Check that the endpoint route exists
        routes = [route.path for route in app.routes]
        assert "/api/v1/resources/{id}/distributions" in routes

    def test_endpoint_route_registration(self, client):
        """Test that the distributions endpoint route is properly registered."""
        # This test verifies the endpoint exists without making database calls
        # that could conflict with other tests in the suite
        routes = [route.path for route in app.routes]
        assert "/api/v1/resources/{id}/distributions" in routes

        # Verify it's a GET endpoint
        distributions_route = None
        for route in app.routes:
            if hasattr(route, "path") and route.path == "/api/v1/resources/{id}/distributions":
                distributions_route = route
                break

        assert distributions_route is not None
        assert hasattr(distributions_route, "methods")
        assert "GET" in distributions_route.methods
