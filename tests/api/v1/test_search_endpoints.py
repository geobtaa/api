import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_suggest_response():
    """Return a mock suggest response for testing."""
    return {
        "suggest": {
            "my-suggestion": [
                {
                    "text": "min",
                    "offset": 0,
                    "length": 3,
                    "options": [
                        {
                            "text": "minnesota",
                            "_id": "test-doc-1",
                            "_score": 0.95,
                            "_source": {"dct_title_s": "Minnesota Map"},
                        },
                        {
                            "text": "mining",
                            "_id": "test-doc-2",
                            "_score": 0.85,
                            "_source": {"dct_title_s": "Mining Data"},
                        },
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_search_endpoint_with_real_data():
    """Test the search endpoint using actual test data."""
    # Call endpoint with a search query that should return results
    response = client.get("/api/v1/search?q=minnesota&page=1&limit=10")

    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Check that we have the expected structure
    assert "meta" in data
    assert "data" in data

    # The response should contain data (actual results depend on test data)
    assert isinstance(data["data"], list)

    # Check that meta contains expected fields
    meta = data["meta"]
    assert "totalCount" in meta
    assert "currentPage" in meta
    assert "perPage" in meta


@pytest.mark.asyncio
async def test_search_with_sort():
    """Test the search endpoint with sorting."""
    # Call endpoint with sort parameter
    response = client.get("/api/v1/search?q=test&sort=year_desc")

    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Should have the expected structure
    assert "meta" in data
    assert "data" in data


@pytest.mark.asyncio
async def test_search_with_filters():
    """Test the search endpoint with filters."""
    # Call endpoint with filter parameters
    response = client.get(
        "/api/v1/search?q=test&fq[dct_spatial_sm][]=Minnesota&fq[schema_provider_s][]=Test%20Provider"
    )

    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Should have the expected structure
    assert "meta" in data
    assert "data" in data


@pytest.mark.asyncio
async def test_suggest_endpoint():
    """Test the suggest endpoint."""
    # Call endpoint
    response = client.get("/api/v1/suggest?q=min")

    # Verify the response
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_search_pagination():
    """Test search pagination."""
    # Test first page
    response1 = client.get("/api/v1/search?q=test&page=1&limit=5")
    assert response1.status_code == 200
    data1 = response1.json()

    # Test second page
    response2 = client.get("/api/v1/search?q=test&page=2&limit=5")
    assert response2.status_code == 200
    data2 = response2.json()

    # Both should have the expected structure
    assert "meta" in data1
    assert "data" in data1
    assert "meta" in data2
    assert "data" in data2


@pytest.mark.asyncio
async def test_search_empty_query():
    """Test search with empty query."""
    response = client.get("/api/v1/search")
    assert response.status_code == 200
    data = response.json()

    # Should still return valid structure
    assert "meta" in data
    assert "data" in data
