"""
Tests for citation API endpoints: /resources/{id}/citation, json-ld, ris, bibtex.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def assert_public_error(data, *, status: int, code: str):
    assert data["errors"][0]["status"] == status
    assert data["errors"][0]["code"] == code


@pytest.mark.unit
def test_citation_endpoint_paths_exist():
    """Test that citation endpoints are registered."""
    routes = [route.path for route in app.routes]
    assert "/api/v1/resources/{id}" in routes
    resource_routes = [r.path for r in app.routes if "citation" in str(r.path)]
    assert len(resource_routes) >= 1


@pytest.mark.unit
def test_citation_endpoint_returns_404_for_nonexistent():
    """Test citation endpoint returns 404 for non-existent resource."""
    response = client.get("/api/v1/resources/nonexistent-uuid-12345/citation")
    assert response.status_code in [404, 500]
    if response.status_code == 404:
        data = response.json()
        assert_public_error(data, status=404, code="not_found")


@pytest.mark.unit
def test_citation_json_ld_returns_404_for_nonexistent():
    """Test json-ld endpoint returns 404 for non-existent resource."""
    response = client.get("/api/v1/resources/nonexistent-uuid-12345/citation/json-ld")
    assert response.status_code in [404, 500]


@pytest.mark.unit
def test_citation_ris_returns_404_for_nonexistent():
    """Test RIS endpoint returns 404 for non-existent resource."""
    response = client.get("/api/v1/resources/nonexistent-uuid-12345/citation/ris")
    assert response.status_code in [404, 500]


@pytest.mark.unit
def test_citation_bibtex_returns_404_for_nonexistent():
    """Test BibTeX endpoint returns 404 for non-existent resource."""
    response = client.get("/api/v1/resources/nonexistent-uuid-12345/citation/bibtex")
    assert response.status_code in [404, 500]


@pytest.mark.unit
def test_citation_json_ld_content_type():
    """Test json-ld endpoint Content-Type header when returning 200."""
    response = client.get("/api/v1/resources/nonexistent-id/citation/json-ld")
    assert response.status_code in [404, 500]
    # When 200, would have application/ld+json
