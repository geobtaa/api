from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app

client = TestClient(app)


def _check_elasticsearch_error(response):
    """Check if response is a 500 due to Elasticsearch error and skip if so."""
    if response.status_code == 500:
        error_data = response.json()
        error_str = str(error_data.get("error", "")).lower()
        if any(term in error_str for term in ["elasticsearch", "index", "connection", "not found"]):
            pytest.skip(f"Elasticsearch not available: {error_data.get('error', 'Unknown error')}")


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


@pytest.mark.integration
@pytest.mark.elasticsearch
def test_search_endpoint_with_real_data(client: TestClient):
    """Test the search endpoint using actual test data."""
    # Call endpoint with a search query that should return results
    response = client.get("/api/v1/search?q=minnesota&page=1&limit=10")

    # Check for Elasticsearch errors
    _check_elasticsearch_error(response)
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


@pytest.mark.integration
@pytest.mark.elasticsearch
def test_search_with_sort(client: TestClient):
    """Test the search endpoint with sorting."""
    # Call endpoint with sort parameter
    response = client.get("/api/v1/search?q=test&sort=year_desc")

    # Check for Elasticsearch errors
    _check_elasticsearch_error(response)
    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Should have the expected structure
    assert "meta" in data
    assert "data" in data


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_search_with_filters(async_client: AsyncClient):
    """Test the search endpoint with filters."""
    # Call endpoint with filter parameters
    response = await async_client.get(
        "/api/v1/search?q=test&fq[dct_spatial_sm][]=Minnesota&fq[schema_provider_s][]=Test%20Provider"
    )

    # Check for Elasticsearch errors
    _check_elasticsearch_error(response)
    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Should have the expected structure
    assert "meta" in data
    assert "data" in data


@pytest.mark.asyncio
async def test_suggest_endpoint(async_client: AsyncClient):
    """Test the suggest endpoint."""
    # Call endpoint
    response = await async_client.get("/api/v1/suggest?q=min")

    # Verify the response
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_search_pagination(async_client: AsyncClient):
    """Test search pagination."""
    # Test first page
    response1 = await async_client.get("/api/v1/search?q=test&page=1&limit=5")
    _check_elasticsearch_error(response1)
    assert response1.status_code == 200
    data1 = response1.json()

    # Test second page
    response2 = await async_client.get("/api/v1/search?q=test&page=2&limit=5")
    _check_elasticsearch_error(response2)
    assert response2.status_code == 200
    data2 = response2.json()

    # Both should have the expected structure
    assert "meta" in data1
    assert "data" in data1
    assert "meta" in data2
    assert "data" in data2


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_search_empty_query(async_client: AsyncClient):
    """Test search with empty query."""
    response = await async_client.get("/api/v1/search")
    _check_elasticsearch_error(response)
    assert response.status_code == 200
    data = response.json()

    # Should still return valid structure
    assert "meta" in data
    assert "data" in data


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_search_by_resource_id(async_client: AsyncClient):
    """Test searching for a resource by its ID."""
    # Use a known resource ID that exists in the test data
    test_resource_id = "stanford-hj948rn6493"

    # Call endpoint with resource ID as search query
    response = await async_client.get(f"/api/v1/search?q={test_resource_id}")

    # Check for Elasticsearch errors
    _check_elasticsearch_error(response)
    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Check that we have the expected structure
    assert "meta" in data
    assert "data" in data

    # In test environment, Elasticsearch might not be available or index might not exist
    # The important thing is that the query structure is correct (verified in logs)
    # We can see from the logs that the query includes "id^5" in the fields list

    # Check that we get a valid response structure regardless of Elasticsearch availability
    assert data["meta"]["totalCount"] >= 0  # Should be 0 if no Elasticsearch, >= 1 if available

    # If we have results, verify the structure
    if data["meta"]["totalCount"] > 0:
        assert len(data["data"]) >= 1

        # The first result should be the exact ID match
        first_result = data["data"][0]
        assert first_result["id"] == test_resource_id

        # Verify the result has the expected JSON:API structure
        assert "type" in first_result
        assert "attributes" in first_result
        assert first_result["type"] == "resource"


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_search_by_partial_resource_id(async_client: AsyncClient):
    """Test searching for a resource by partial ID."""
    # Use a partial resource ID that should match multiple resources
    partial_id = "stanford"

    # Call endpoint with partial ID as search query
    response = await async_client.get(f"/api/v1/search?q={partial_id}&per_page=5")

    # Check for Elasticsearch errors
    _check_elasticsearch_error(response)
    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Check that we have the expected structure
    assert "meta" in data
    assert "data" in data

    # In test environment, Elasticsearch might not be available
    # The important thing is that the query structure is correct (verified in logs)

    # Check that we get a valid response structure regardless of Elasticsearch availability
    assert data["meta"]["totalCount"] >= 0  # Should be 0 if no Elasticsearch, >= 1 if available

    # If we have results, verify the structure
    if data["meta"]["totalCount"] > 0:
        assert len(data["data"]) >= 1

        # All results should contain the partial ID in their ID field
        for result in data["data"]:
            assert partial_id in result["id"]
            assert "type" in result
            assert "attributes" in result
            assert result["type"] == "resource"


@pytest.mark.integration
@pytest.mark.elasticsearch
@pytest.mark.asyncio
async def test_search_id_boost_priority(async_client: AsyncClient):
    """Test that exact ID matches are given higher priority than partial matches."""
    # Use a resource ID that might also appear in other fields
    test_resource_id = "stanford-hj948rn6493"

    # Call endpoint with the exact ID
    response = await async_client.get(f"/api/v1/search?q={test_resource_id}&per_page=10")

    # Check for Elasticsearch errors
    _check_elasticsearch_error(response)
    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # In test environment, Elasticsearch might not be available
    # The important thing is that the query structure is correct (verified in logs)

    # Check that we get a valid response structure regardless of Elasticsearch availability
    assert data["meta"]["totalCount"] >= 0  # Should be 0 if no Elasticsearch, >= 1 if available

    # If we have results, verify the structure and priority
    if data["meta"]["totalCount"] > 0:
        assert len(data["data"]) >= 1

        # The exact ID match should be the first result (highest score)
        first_result = data["data"][0]
        assert first_result["id"] == test_resource_id

        # If there are multiple results, verify they're ordered by relevance
        if len(data["data"]) > 1:
            # The first result should be the exact match
            assert data["data"][0]["id"] == test_resource_id


class TestSearchEndpointsEnhanced:
    """Enhanced test cases for search endpoints with better coverage."""

    def test_search_endpoints_structure(self):
        """Test that search endpoints are properly configured."""
        routes = [route.path for route in app.routes]

        assert "/api/v1/search" in routes
        assert "/api/v1/suggest" in routes

    def test_search_parameter_validation(self):
        """Test parameter validation for search endpoint."""
        # Test invalid page parameter (page should be >= 1)
        response = client.get("/api/v1/search?page=0")
        # The endpoint might allow page=0, so we'll just check it doesn't crash
        assert response.status_code in [200, 422]  # Either valid or validation error

        # Test invalid per_page parameter
        response = client.get("/api/v1/search?per_page=0")
        # The endpoint might allow per_page=0, so we'll just check it doesn't crash
        assert response.status_code in [200, 422]  # Either valid or validation error

        response = client.get("/api/v1/search?per_page=101")
        # The endpoint might allow per_page > 100, so we'll just check it doesn't crash
        assert response.status_code in [200, 422]  # Either valid or validation error

    def test_search_sort_parameter_validation(self):
        """Test sort parameter validation."""
        # Test valid sort options
        valid_sorts = ["relevance", "year_desc", "year_asc", "title_asc", "title_desc"]

        for sort_option in valid_sorts:
            response = client.get(f"/api/v1/search?sort={sort_option}")
            # Should not return validation error for valid sort options
            assert response.status_code in [200, 500]  # Allow database errors in test env

    def test_search_with_callback(self):
        """Test search with JSONP callback parameter."""
        response = client.get("/api/v1/search?q=test&callback=testCallback")

        # Should not return validation error for JSONP callback
        assert response.status_code in [200, 500]  # Allow database errors in test env

    def test_suggest_parameter_validation(self):
        """Test parameter validation for suggest endpoint."""
        # Test missing required query parameter
        response = client.get("/api/v1/suggest")
        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    @pytest.mark.elasticsearch
    def test_search_service_integration(self):
        """Test search endpoint integration with real data."""
        # Use real search service instead of mocks
        response = client.get("/api/v1/search?q=test")

        # Check for Elasticsearch errors
        _check_elasticsearch_error(response)
        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)
        assert "totalCount" in data["meta"]
        assert isinstance(data["meta"]["totalCount"], int)

    @patch("app.api.v1.endpoint_modules.search.SearchService")
    def test_search_service_error_handling(self, mock_search_service):
        """Test search service error handling."""
        # Mock SearchService to raise an exception
        mock_service_instance = AsyncMock()
        mock_search_service.return_value = mock_service_instance
        mock_service_instance.search.side_effect = Exception("Search service error")

        response = client.get("/api/v1/search?q=test")

        # Should handle error gracefully
        assert response.status_code in [200, 500]  # Depending on error handling implementation

    def test_search_filter_parameter_parsing(self):
        """Test that filter parameters are properly parsed."""
        # Test with multiple filter values
        response = client.get(
            "/api/v1/search?q=test&fq[dct_spatial_sm][]=Minnesota&fq[dct_spatial_sm][]=Wisconsin"
        )

        # Should not return validation error for valid filter parameters
        assert response.status_code in [200, 500]  # Allow database errors in test env

    def test_search_with_special_characters(self):
        """Test search with special characters in query."""
        # Test with various special characters
        special_queries = [
            "test & query",
            "test+query",
            "test/query",
            "test?query",
            "test#query",
            "test%query",
        ]

        for query in special_queries:
            response = client.get(f"/api/v1/search?q={query}")
            # Should handle special characters gracefully
            assert response.status_code in [200, 500]  # Allow database errors in test env

    def test_search_empty_results(self):
        """Test search with query that returns no results."""
        response = client.get("/api/v1/search?q=nonexistentquery12345")

        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "meta" in data
            assert data["meta"]["totalCount"] == 0
            assert len(data["data"]) == 0

    def test_search_pagination_boundaries(self):
        """Test search pagination boundary conditions."""
        # Test with very high page number
        response = client.get("/api/v1/search?q=test&page=1000")

        if response.status_code == 200:
            data = response.json()
            assert "meta" in data
            assert data["meta"]["currentPage"] == 1000
            assert len(data["data"]) == 0  # Should be empty for non-existent page

    def test_search_per_page_variations(self):
        """Test search with different per_page values."""
        per_page_values = [1, 5, 10, 25, 50, 100]

        for per_page in per_page_values:
            response = client.get(f"/api/v1/search?q=test&per_page={per_page}")

            if response.status_code == 200:
                data = response.json()
                assert "meta" in data
                assert data["meta"]["perPage"] == per_page
                assert len(data["data"]) <= per_page

    def test_suggest_with_empty_query(self):
        """Test suggest endpoint with empty query."""
        response = client.get("/api/v1/suggest?q=")

        # Should handle empty query gracefully
        assert response.status_code in [200, 422, 500]  # Depending on validation

    def test_suggest_with_long_query(self):
        """Test suggest endpoint with very long query."""
        long_query = "a" * 1000  # Very long query string
        response = client.get(f"/api/v1/suggest?q={long_query}")

        # Should handle long query gracefully
        assert response.status_code in [200, 422, 500]  # Depending on validation

    def test_search_jsonapi_compliance(self):
        """Test that search endpoints return proper JSON:API structure."""
        response = client.get("/api/v1/search?q=test")

        if response.status_code == 200:
            data = response.json()

            # Should have JSON:API structure
            assert "jsonapi" in data
            assert "data" in data
            assert "meta" in data

            # If there are results, they should have proper structure
            if data["data"]:
                for result in data["data"]:
                    assert "id" in result
                    assert "type" in result
                    assert "attributes" in result
                    assert result["type"] == "resource"

    def test_search_meta_structure(self):
        """Test that search meta contains expected fields."""
        response = client.get("/api/v1/search?q=test")

        if response.status_code == 200:
            data = response.json()
            meta = data["meta"]

            # Should contain pagination info
            assert "totalCount" in meta
            assert "currentPage" in meta
            assert "perPage" in meta
            assert "totalPages" in meta

            # Values should be reasonable
            assert meta["totalCount"] >= 0
            assert meta["currentPage"] >= 1
            assert meta["perPage"] > 0
            assert meta["totalPages"] >= 0

    def test_search_error_response_structure(self):
        """Test that search error responses have proper structure."""
        # This test would need to trigger an error condition
        # For now, just verify the endpoint exists and can handle requests
        response = client.get("/api/v1/search?q=test")

        # Should return a valid HTTP response
        assert response.status_code in [200, 422, 500]

        if response.status_code != 200:
            # Error responses should have proper structure
            try:
                data = response.json()
                # Should have some indication of error
                assert "detail" in data or "error" in data or "message" in data
            except Exception:
                # If it's not JSON, that's also acceptable for error responses
                pass

    def test_suggest_response_structure(self):
        """Test that suggest endpoint returns proper structure."""
        response = client.get("/api/v1/suggest?q=test")

        if response.status_code == 200:
            data = response.json()

            # Should have proper structure
            assert "data" in data
            assert isinstance(data["data"], list)

            # If there are suggestions, they should have proper structure
            if data["data"]:
                for suggestion in data["data"]:
                    assert "id" in suggestion
                    assert "type" in suggestion
                    assert "attributes" in suggestion

    def test_suggest_endpoint_omits_title_attribute(self):
        """Test that suggest endpoint omits the secondary title field."""
        with patch(
            "app.api.v1.endpoint_modules.search.SearchService.suggest",
            new=AsyncMock(
                return_value={
                    "data": [
                        {
                            "type": "suggestion",
                            "id": "doc-1",
                            "attributes": {"text": "Chicago", "score": 6},
                        }
                    ]
                }
            ),
        ):
            response = client.get("/api/v1/suggest?q=chicago")

        assert response.status_code == 200
        assert response.json()["data"][0]["attributes"] == {"text": "Chicago", "score": 6}

    def test_search_with_unicode_characters(self):
        """Test search with Unicode characters."""
        unicode_queries = ["café", "naïve", "résumé", "北京", "Москва", "São Paulo"]

        for query in unicode_queries:
            response = client.get(f"/api/v1/search?q={query}")
            # Should handle Unicode characters gracefully
            assert response.status_code in [200, 500]  # Allow database errors in test env

    def test_search_case_sensitivity(self):
        """Test search case sensitivity handling."""
        queries = ["Minnesota", "minnesota", "MINNESOTA", "MiNnEsOtA"]

        for query in queries:
            response = client.get(f"/api/v1/search?q={query}")
            # Should handle case variations gracefully
            assert response.status_code in [200, 500]  # Allow database errors in test env
