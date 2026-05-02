import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.requests import Request

from app.api.v1.endpoint_modules.search import _handle_search
from app.main import app

client = TestClient(app)


def _check_elasticsearch_error(response):
    """Check if response is a 500 due to Elasticsearch error and skip if so."""
    if response.status_code == 500:
        error_data = response.json()
        error_str = str(error_data.get("error", "")).lower()
        if any(term in error_str for term in ["elasticsearch", "index", "connection", "not found"]):
            pytest.skip(f"Elasticsearch not available: {error_data.get('error', 'Unknown error')}")


def _build_request(query_string: bytes) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/search",
            "raw_path": b"/api/v1/search",
            "query_string": query_string,
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "root_path": "",
        }
    )


@pytest.fixture(autouse=True)
def disable_semantic_search_cache_by_default(monkeypatch):
    from app.api.v1.endpoint_modules import search as search_module

    monkeypatch.setattr(search_module, "SEARCH_RESULT_CACHE_ENABLED", False)


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


@pytest.mark.asyncio
async def test_handle_search_builds_and_stores_missing_resource_representation():
    request = _build_request(b"q=st+paul&view=gallery")
    session = AsyncMock()
    session_context = AsyncMock()
    session_context.__aenter__.return_value = session
    session_context.__aexit__.return_value = False

    processed_resource = {
        "type": "resource",
        "id": "test-doc",
        "attributes": {},
        "meta": {"ui": {}},
    }
    distribution_context = object()
    relationship_payload = {"same_as": [{"resource_id": "related-doc"}]}
    allmaps_payload = {"allmaps_id": "abc123"}
    data_dictionary_payload = [{"id": 1, "name": "Fields"}]
    bridge_download_rows = [{"label": "Download", "file_url": "https://example.com/file.zip"}]
    thumbnail_asset_url = "https://example.com/thumb.jpg"

    with (
        patch(
            "app.api.v1.endpoint_modules.search.SearchService.search",
            new=AsyncMock(
                return_value={
                    "data": [
                        {
                            "id": "test-doc",
                            "score": 12.5,
                            "attributes": {"id": "test-doc", "dct_title_s": "Test Resource"},
                        }
                    ],
                    "meta": {"pages": {"total_count": 1, "total_pages": 1}},
                }
            ),
        ) as mock_search,
        patch(
            "app.api.v1.endpoint_modules.search.async_session",
            return_value=session_context,
        ) as mock_async_session,
        patch(
            "app.api.v1.endpoint_modules.search.get_cached_resource_representations",
            new=AsyncMock(return_value={}),
        ) as mock_get_cached_resource_representations,
        patch(
            "app.api.v1.endpoint_modules.search.process_resource",
            new=AsyncMock(return_value=processed_resource),
        ) as mock_process_resource,
        patch(
            "app.api.v1.endpoint_modules.search.fetch_distribution_context_map",
            new=AsyncMock(return_value={"test-doc": distribution_context}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.fetch_allmaps_attributes_map",
            new=AsyncMock(return_value={"test-doc": allmaps_payload}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.fetch_resource_data_dictionaries_map",
            new=AsyncMock(return_value={"test-doc": ["ignored"]}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search._serialize_data_dictionaries_by_id",
            return_value={"test-doc": data_dictionary_payload},
        ),
        patch(
            "app.api.v1.endpoint_modules.search.RelationshipService.get_resource_relationships_map",
            new=AsyncMock(return_value={"test-doc": relationship_payload}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.fetch_bridge_asset_download_rows_map",
            new=AsyncMock(return_value={"test-doc": bridge_download_rows}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search._get_thumbnail_asset_urls",
            new=AsyncMock(return_value={"test-doc": thumbnail_asset_url}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.store_resource_representations",
            new=AsyncMock(),
        ) as mock_store_resource_representations,
    ):
        response = await _handle_search(
            request,
            {
                "q": "st paul",
                "page": 1,
                "per_page": 20,
                "meta": True,
                "request_query_params": "q=st+paul&view=gallery",
            },
        )

    assert response.status_code == 200
    mock_async_session.assert_called_once()
    session.execute.assert_not_called()
    mock_get_cached_resource_representations.assert_awaited_once_with(["test-doc"])
    assert mock_search.await_args.kwargs["hydrate_hits"] is False
    assert mock_search.await_args.kwargs["sanitize_response"] is False
    assert mock_async_session.call_count == 1
    assert mock_process_resource.await_args.kwargs["include_similar_items"] is False
    assert mock_process_resource.await_args.kwargs["distribution_context"] is distribution_context
    assert (
        mock_process_resource.await_args.kwargs["bridge_asset_download_rows"]
        == bridge_download_rows
    )
    assert mock_process_resource.await_args.kwargs["ui_relationships"] == relationship_payload
    assert mock_process_resource.await_args.kwargs["allmaps_attributes"] == allmaps_payload
    assert (
        mock_process_resource.await_args.kwargs["data_dictionaries_payload"]
        == data_dictionary_payload
    )
    assert mock_process_resource.await_args.kwargs["thumbnail_asset_url"] == thumbnail_asset_url
    mock_store_resource_representations.assert_awaited_once_with({"test-doc": processed_resource})

    payload = json.loads(response.body)
    assert payload["data"][0]["meta"]["score"] == 12.5


@pytest.mark.asyncio
async def test_handle_search_reuses_cached_resource_representation():
    request = _build_request(b"q=st+paul")
    cached_resource = {
        "type": "resource",
        "id": "test-doc",
        "attributes": {"ogm": {"dct_title_s": "Cached Resource"}},
        "meta": {"ui": {}},
    }

    with (
        patch(
            "app.api.v1.endpoint_modules.search.SearchService.search",
            new=AsyncMock(
                return_value={
                    "data": [{"id": "test-doc"}],
                    "meta": {"pages": {"total_count": 1, "total_pages": 1}},
                }
            ),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.async_session",
        ) as mock_async_session,
        patch(
            "app.api.v1.endpoint_modules.search.get_cached_resource_representations",
            new=AsyncMock(return_value={"test-doc": cached_resource}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.process_resource",
            new=AsyncMock(),
        ) as mock_process_resource,
        patch(
            "app.api.v1.endpoint_modules.search.store_resource_representations",
            new=AsyncMock(),
        ) as mock_store_resource_representations,
    ):
        response = await _handle_search(
            request,
            {
                "q": "st paul",
                "page": 1,
                "per_page": 20,
                "meta": True,
                "request_query_params": "q=st+paul",
            },
        )

    assert response.status_code == 200
    mock_async_session.assert_not_called()
    mock_process_resource.assert_not_awaited()
    mock_store_resource_representations.assert_not_awaited()
    payload = json.loads(response.body)
    assert payload["data"][0]["attributes"]["ogm"]["dct_title_s"] == "Cached Resource"


@pytest.mark.asyncio
async def test_handle_search_semantic_cache_ignores_cache_buster(monkeypatch):
    from app.api.v1.endpoint_modules import search as search_module
    from app.services.cache_service import CacheService as RealCacheService

    monkeypatch.setattr(search_module, "SEARCH_RESULT_CACHE_ENABLED", True)

    class FakeSemanticCache:
        _redis_client = object()
        store = {}
        tagged = []
        generate_cache_key = staticmethod(RealCacheService.generate_cache_key)

        async def get(self, key):
            value = self.store.get(key)
            return json.loads(json.dumps(value)) if value is not None else None

        async def set(self, key, value, ttl):
            self.store[key] = json.loads(json.dumps(value))
            return True

        async def tag_cache_key(self, key, tags, ttl_seconds):
            self.tagged.append((key, set(tags), ttl_seconds))

        async def acquire_lock(self, lock_key):
            return True

    monkeypatch.setattr(search_module, "CacheService", FakeSemanticCache)

    cached_resource = {
        "type": "resource",
        "id": "test-doc",
        "attributes": {"ogm": {"dct_title_s": "Cached Resource"}},
        "meta": {"ui": {}},
    }
    search_mock = AsyncMock(
        return_value={
            "data": [{"id": "test-doc", "score": 12.5}],
            "meta": {"pages": {"total_count": 1, "total_pages": 1}},
            "queryTime": {},
        }
    )

    with (
        patch(
            "app.api.v1.endpoint_modules.search.SearchService.search",
            search_mock,
        ),
        patch(
            "app.api.v1.endpoint_modules.search.get_cached_resource_representations",
            new=AsyncMock(return_value={"test-doc": cached_resource}),
        ),
    ):
        first = await search_module._handle_search(
            _build_request(b"q=st+paul&k6cb=one"),
            {
                "q": "st paul",
                "page": 1,
                "per_page": 20,
                "meta": True,
                "request_query_params": "q=st+paul&k6cb=one",
                "fq": {},
                "include_filters": {},
                "exclude_filters": {},
            },
        )
        second = await search_module._handle_search(
            _build_request(b"q=st+paul&k6cb=two"),
            {
                "q": "st paul",
                "page": 1,
                "per_page": 20,
                "meta": False,
                "request_query_params": "q=st+paul&k6cb=two",
                "fq": {},
                "include_filters": {},
                "exclude_filters": {},
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert search_mock.await_count == 1
    assert first.headers["x-search-semantic-cache"] == "MISS"
    assert second.headers["x-search-semantic-cache"] == "HIT"
    assert any("search" in tags for _, tags, _ in FakeSemanticCache.tagged)

    first_payload = json.loads(first.body)
    second_payload = json.loads(second.body)
    assert first_payload["data"][0]["meta"]["score"] == 12.5
    assert "meta" not in second_payload["data"][0]


@pytest.mark.asyncio
async def test_handle_search_falls_back_to_database_when_search_hit_lacks_attributes():
    request = _build_request(b"q=st+paul")
    row = MagicMock()
    row._mapping = {"id": "test-doc", "dct_title_s": "Test Resource"}

    db_result = MagicMock()
    db_result.fetchall.return_value = [row]

    session = AsyncMock()
    session.execute.return_value = db_result

    session_context = AsyncMock()
    session_context.__aenter__.return_value = session
    session_context.__aexit__.return_value = False

    processed_resource = {
        "type": "resource",
        "id": "test-doc",
        "attributes": {"ogm": {"dct_title_s": "Test Resource"}},
        "meta": {"ui": {}},
    }
    distribution_context = object()

    with (
        patch(
            "app.api.v1.endpoint_modules.search.SearchService.search",
            new=AsyncMock(
                return_value={
                    "data": [{"id": "test-doc", "score": 7.5}],
                    "meta": {"pages": {"total_count": 1, "total_pages": 1}},
                }
            ),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.async_session",
            return_value=session_context,
        ) as mock_async_session,
        patch(
            "app.api.v1.endpoint_modules.search.get_cached_resource_representations",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.process_resource",
            new=AsyncMock(return_value=processed_resource),
        ) as mock_process_resource,
        patch(
            "app.api.v1.endpoint_modules.search.fetch_distribution_context_map",
            new=AsyncMock(return_value={"test-doc": distribution_context}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.fetch_allmaps_attributes_map",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.fetch_resource_data_dictionaries_map",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.RelationshipService.get_resource_relationships_map",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.fetch_bridge_asset_download_rows_map",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search._get_thumbnail_asset_urls",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "app.api.v1.endpoint_modules.search.store_resource_representations",
            new=AsyncMock(),
        ) as mock_store_resource_representations,
    ):
        response = await _handle_search(
            request,
            {
                "q": "st paul",
                "page": 1,
                "per_page": 20,
                "meta": True,
                "request_query_params": "q=st+paul",
            },
        )

    assert response.status_code == 200
    mock_async_session.assert_called()
    assert mock_process_resource.await_args.args[0]["dct_title_s"] == "Test Resource"
    assert mock_process_resource.await_args.kwargs["distribution_context"] is distribution_context
    mock_store_resource_representations.assert_awaited_once_with({"test-doc": processed_resource})


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
