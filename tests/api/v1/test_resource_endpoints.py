import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services.relationship_service import RelationshipService

client = TestClient(app)


@pytest.fixture
def mock_resource():
    """Return a mock resource for testing."""
    return {
        "id": "test-resource-id",
        "dct_title_s": "Test Resource Title",
        "dct_description_sm": ["This is a test resource description"],
        "dct_creator_sm": ["Test Creator"],
        "dct_publisher_sm": ["Test Publisher"],
        "dct_references_s": json.dumps(
            {
                "http://schema.org/downloadUrl": "https://example.com/download",
                "http://iiif.io/api/image": "https://example.com/iiif/image",
            }
        ),
        "dc_format_s": "PDF",
        "gbl_resourcetype_sm": ["Maps"],
        "gbl_resourceclass_sm": ["Datasets"],
        "dct_spatial_sm": ["Minnesota"],
        "dct_rights_sm": ["Public"],
        "schema_provider_s": "Test Provider",
    }


@pytest.fixture
def mock_relationships():
    """Return mock relationships for testing."""
    return {
        "isPartOf": [
            {
                "resource_id": "related-resource-1",
                "resource_title": "Related Resource 1",
                "link": "http://localhost:8000/api/v1/resources/related-resource-1",
            }
        ],
        "hasPart": [
            {
                "resource_id": "related-resource-2",
                "resource_title": "Related Resource 2",
                "link": "http://localhost:8000/api/v1/resources/related-resource-2",
            }
        ],
    }


@pytest.fixture
def mock_summaries():
    """Return mock AI summaries for testing."""
    return [
        {
            "id": 1,
            "resource_id": "test-resource-id",
            "type": "summary",
            "content": "This is a test AI-generated summary.",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }
    ]


@pytest.mark.asyncio
@patch("app.services.search_service.SearchService.get_resource")
async def test_get_resource(
    mock_get_resource,
    mock_resource,
    mock_relationships,
    mock_summaries,
):
    """Test the get_resource endpoint."""
    # Setup mock response from SearchService
    mock_get_resource.return_value = {
        "data": {
            "type": "resource",
            "id": mock_resource["id"],
            "attributes": {
                **mock_resource,
                "ui_thumbnail_url": "https://example.com/thumbnail.jpg",
                "ui_citation": "Test Citation",
                "ui_downloads": {"pdf": "https://example.com/download.pdf"},
                "ui_relationships": mock_relationships,
                "ui_summaries": mock_summaries,
                "ui_viewer_endpoint": "https://example.com/viewer",
                "ui_viewer_geometry": "POINT(0 0)",
                "ui_viewer_protocol": "iiif",
            },
        }
    }

    # Call endpoint
    response = client.get(f"/api/v1/resources/{mock_resource['id']}")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["id"] == mock_resource["id"]
    assert data["data"]["attributes"]["dct_title_s"] == mock_resource["dct_title_s"]
    assert "ui_thumbnail_url" in data["data"]["attributes"]
    assert "ui_citation" in data["data"]["attributes"]
    assert "ui_downloads" in data["data"]["attributes"]
    assert "ui_relationships" in data["data"]["attributes"]
    assert data["data"]["attributes"]["ui_relationships"] == mock_relationships
    assert "ui_summaries" in data["data"]["attributes"]


@pytest.mark.asyncio
@patch("app.services.search_service.SearchService.get_resource")
async def test_get_resource_not_found(mock_get_resource):
    """Test the get_resource endpoint with non-existent ID."""

    # Setup mock to raise NotFoundError
    async def raise_not_found(*args, **kwargs):
        raise HTTPException(status_code=404, detail="Resource not found")

    mock_get_resource.side_effect = raise_not_found

    # Call endpoint
    response = client.get("/api/v1/resources/non-existent-id")

    # Verify response
    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found"


@pytest.mark.skip(reason="Requires database setup with test data")
def test_list_resources():
    """Test the list_resources endpoint exists."""
    # This test requires database setup with test data
    # For now, just verify the endpoint exists
    pass


def test_relationship_service_initialization():
    """Test that RelationshipService can be initialized."""
    # Simple test that the service can be created
    service = RelationshipService()
    assert service is not None
    assert hasattr(service, "get_resource_relationships")
