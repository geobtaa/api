import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app


@pytest.fixture
def client():
    """Return a FastAPI test client."""
    return TestClient(app)


@pytest.fixture(scope="function")
async def async_client():
    """Return an async HTTP client for testing."""
    from httpx import ASGITransport

    from db.database import database

    # Always disconnect and reconnect to ensure we're using this event loop's connection pool
    # This avoids "Future attached to a different loop" errors when running multiple tests
    try:
        await database.disconnect()
    except Exception:
        pass  # Ignore errors if not connected
    await database.connect()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        try:
            yield ac
        finally:
            # Clean up: disconnect after test to avoid connection pool issues
            try:
                await database.disconnect()
            except Exception:
                pass


@pytest.fixture
def mock_item():
    """Return a mock item for testing."""
    return {
        "id": "test-item-id",
        "dct_title_s": "Test Item Title",
        "dct_description_sm": ["This is a test item description"],
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
def mock_elasticsearch_response():
    """Return a mock Elasticsearch response."""
    mock_response = MagicMock()
    mock_response.meta.status = 200
    mock_response.took = 10
    mock_response.body = {
        "took": 10,
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "hits": [
                {
                    "_score": 9.5,
                    "_id": "test-doc-1",
                    "_source": {
                        "id": "test-doc-1",
                        "dct_title_s": "Test Document 1",
                        "dct_description_sm": ["Test description 1"],
                    },
                },
                {
                    "_score": 8.2,
                    "_id": "test-doc-2",
                    "_source": {
                        "id": "test-doc-2",
                        "dct_title_s": "Test description 2",
                    },
                },
            ],
        },
        "aggregations": {
            "resource_type_agg": {
                "buckets": [{"key": "Maps", "doc_count": 1}, {"key": "Datasets", "doc_count": 1}]
            }
        },
    }
    return mock_response


@pytest.fixture
def mock_task():
    """Return a mock celery task."""
    task = MagicMock()
    task.id = "test-task-id"
    return task
