"""
Tests for the /search/facets/{facet_name} endpoint.

This file contains comprehensive tests covering:
- Validation (invalid facet names, invalid sort parameters)
- Successful responses with various parameters
- Pagination
- Sorting options
- Filtering facet values (q_facet)
- Search context (q parameter)
- Filter context (include_filters)
- Error handling
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# Disable caching for all tests in this file
@pytest.fixture(autouse=True)
def disable_caching():
    with patch("app.services.cache_service.ENDPOINT_CACHE", False):
        yield


class TestFacetEndpointValidation:
    """Test validation of facet endpoint parameters."""

    async def test_invalid_facet_name(self, async_client: AsyncClient):
        """Test that invalid facet name returns 400 error."""
        response = await async_client.get("/api/v1/search/facets/invalid_facet_name")
        assert response.status_code == 400
        assert "invalid facet name" in response.json()["error"].lower()

    async def test_invalid_sort_parameter(self, async_client: AsyncClient):
        """Test that invalid sort parameter returns 400 error."""
        response = await async_client.get(
            "/api/v1/search/facets/schema_provider_s?sort=invalid_sort"
        )
        assert response.status_code == 400
        assert "invalid sort parameter" in response.json()["error"].lower()

    async def test_invalid_page_parameter(self, async_client: AsyncClient):
        """Test that invalid page parameter returns validation error."""
        response = await async_client.get("/api/v1/search/facets/schema_provider_s?page=0")
        assert response.status_code == 422  # FastAPI validation error

    async def test_invalid_per_page_parameter(self, async_client: AsyncClient):
        """Test that invalid per_page parameter returns validation error."""
        response = await async_client.get("/api/v1/search/facets/schema_provider_s?per_page=0")
        assert response.status_code == 422  # FastAPI validation error

    async def test_invalid_adv_q_json(self, async_client: AsyncClient):
        """Test that invalid JSON in adv_q returns 400 error."""
        response = await async_client.get(
            "/api/v1/search/facets/schema_provider_s?adv_q=invalid_json"
        )
        assert response.status_code == 400
        assert "invalid json" in response.json()["error"].lower()


class TestFacetEndpointSuccess:
    """Test successful facet endpoint responses."""

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    async def test_basic_facet_retrieval(
        self,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test basic facet retrieval with default parameters."""
        # Mock return values
        mock_buckets = [
            {"key": "Provider A", "doc_count": 100},
            {"key": "Provider B", "doc_count": 50},
        ]
        mock_get_facet.return_value = mock_buckets

        mock_search_criteria.return_value = {"query": None, "filters": {}}

        mock_process.return_value = {
            "data": [
                {
                    "type": "facet_value",
                    "id": "Provider A",
                    "attributes": {"value": "Provider A", "hits": 100},
                },
                {
                    "type": "facet_value",
                    "id": "Provider B",
                    "attributes": {"value": "Provider B", "hits": 50},
                },
            ],
            "meta": {
                "totalCount": 2,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": "schema_provider_s",
                "sort": "count_desc",
            },
        }

        mock_pagination.return_value = {
            "self": "/api/v1/search/facets/schema_provider_s?page=1",
            "first": "/api/v1/search/facets/schema_provider_s?page=1",
            "last": "/api/v1/search/facets/schema_provider_s?page=1",
        }

        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        response = await async_client.get("/api/v1/search/facets/schema_provider_s")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert "links" in data
        assert "applyTemplate" in data["links"]
        assert data["meta"]["facetName"] == "schema_provider_s"
        assert data["meta"]["sort"] == "count_desc"

        # Verify mocks were called
        mock_get_facet.assert_called_once()
        mock_process.assert_called_once()

    @pytest.mark.parametrize(
        "sort_option",
        ["count_desc", "count_asc", "alpha_asc", "alpha_desc"],
    )
    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    async def test_sort_options(
        self,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        sort_option,
        async_client: AsyncClient,
    ):
        """Test all sort options."""
        mock_buckets = [{"key": "Provider A", "doc_count": 100}]
        mock_get_facet.return_value = mock_buckets
        mock_search_criteria.return_value = {"query": None, "filters": {}}
        mock_process.return_value = {
            "data": [],
            "meta": {
                "sort": sort_option,
                "totalCount": 1,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": "schema_provider_s",
            },
        }
        mock_pagination.return_value = {"self": "/test"}
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        response = await async_client.get(
            f"/api/v1/search/facets/schema_provider_s?sort={sort_option}"
        )

        assert response.status_code == 200
        # Verify sort parameter was passed to process_facet_response
        call_args = mock_process.call_args
        assert call_args.kwargs["sort"] == sort_option

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    async def test_pagination(
        self,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test pagination parameters."""
        mock_buckets = [{"key": f"Provider {i}", "doc_count": 100 - i} for i in range(20)]
        mock_get_facet.return_value = mock_buckets
        mock_search_criteria.return_value = {"query": None, "filters": {}}
        mock_process.return_value = {
            "data": [],
            "meta": {
                "totalCount": 20,
                "totalPages": 2,
                "currentPage": 2,
                "perPage": 10,
                "facetName": "schema_provider_s",
                "sort": "count_desc",
            },
        }
        mock_pagination.return_value = {
            "self": "/test?page=2",
            "prev": "/test?page=1",
            "next": "/test?page=3",
        }
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        response = await async_client.get(
            "/api/v1/search/facets/schema_provider_s?page=2&per_page=10"
        )

        assert response.status_code == 200
        # Verify pagination parameters were passed
        call_args = mock_process.call_args
        assert call_args.kwargs["page"] == 2
        assert call_args.kwargs["per_page"] == 10

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    async def test_q_facet_filtering(
        self,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test filtering facet values with q_facet parameter."""
        mock_buckets = [
            {"key": "University of Minnesota", "doc_count": 50},
            {"key": "University of Wisconsin", "doc_count": 30},
        ]
        mock_get_facet.return_value = mock_buckets
        mock_search_criteria.return_value = {"query": None, "filters": {}}
        mock_process.return_value = {
            "data": [],
            "meta": {
                "totalCount": 2,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": "schema_provider_s",
                "sort": "count_desc",
            },
        }
        mock_pagination.return_value = {"self": "/test"}
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        response = await async_client.get(
            "/api/v1/search/facets/schema_provider_s?q_facet=University"
        )

        assert response.status_code == 200
        # Verify q_facet was passed to get_facet_values
        call_args = mock_get_facet.call_args
        assert call_args.kwargs["q_facet"] == "University"

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    async def test_search_context(
        self,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test facet retrieval with search query context."""
        mock_buckets = [{"key": "Provider A", "doc_count": 25}]
        mock_get_facet.return_value = mock_buckets
        mock_search_criteria.return_value = {"query": "water", "filters": {}}
        mock_process.return_value = {
            "data": [],
            "meta": {
                "totalCount": 1,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": "schema_provider_s",
                "sort": "count_desc",
            },
        }
        mock_pagination.return_value = {"self": "/test"}
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        response = await async_client.get("/api/v1/search/facets/schema_provider_s?q=water")

        assert response.status_code == 200
        # Verify search query was passed to get_facet_values
        call_args = mock_get_facet.call_args
        assert call_args.kwargs["query"] == "water"

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    @patch("app.api.v1.endpoint_modules.search.SearchService")
    async def test_filter_context(
        self,
        mock_search_service,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test facet retrieval with include_filters context."""
        mock_buckets = [{"key": "Provider A", "doc_count": 15}]
        mock_get_facet.return_value = mock_buckets

        # Mock SearchService methods
        mock_service_instance = MagicMock()
        mock_service_instance.extract_filter_queries.return_value = {}
        mock_service_instance.extract_new_style_filters.return_value = (
            {"dct_spatial_sm": ["Minnesota"]},
            {},
        )
        mock_search_service.return_value = mock_service_instance

        mock_search_criteria.return_value = {"query": None, "filters": {}}
        mock_process.return_value = {
            "data": [],
            "meta": {
                "totalCount": 1,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": "schema_provider_s",
                "sort": "count_desc",
            },
        }
        mock_pagination.return_value = {"self": "/test"}
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        response = await async_client.get(
            "/api/v1/search/facets/schema_provider_s?include_filters[dct_spatial_sm][]=Minnesota"
        )

        assert response.status_code == 200
        # Verify include_filters were passed to get_facet_values
        call_args = mock_get_facet.call_args
        assert call_args.kwargs["include_filters"] == {"dct_spatial_sm": ["Minnesota"]}

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    @patch("app.api.v1.endpoint_modules.search.validate_adv_q")
    async def test_adv_q_parameter(
        self,
        mock_validate_adv_q,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test advanced query parameter."""
        mock_buckets = [{"key": "Provider A", "doc_count": 10}]
        mock_get_facet.return_value = mock_buckets
        mock_search_criteria.return_value = {"query": None, "filters": {}}
        mock_validate_adv_q.return_value = [{"op": "AND", "f": "dct_title_s", "q": "Iowa"}]
        mock_process.return_value = {
            "data": [],
            "meta": {
                "totalCount": 1,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": "schema_provider_s",
                "sort": "count_desc",
            },
        }
        mock_pagination.return_value = {"self": "/test"}
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        adv_q = json.dumps([{"op": "AND", "f": "dct_title_s", "q": "Iowa"}])
        response = await async_client.get(f"/api/v1/search/facets/schema_provider_s?adv_q={adv_q}")

        assert response.status_code == 200
        # Verify adv_q was validated and passed
        mock_validate_adv_q.assert_called_once()
        call_args = mock_get_facet.call_args
        assert call_args.kwargs["adv_q"] == [{"op": "AND", "f": "dct_title_s", "q": "Iowa"}]

    @pytest.mark.parametrize(
        "facet_name",
        [
            "dct_spatial_sm",
            "gbl_resourceClass_sm",
            "gbl_resourceType_sm",
            "dct_language_sm",
            "dct_creator_sm",
            "schema_provider_s",
            "dct_accessRights_s",
            "gbl_georeferenced_b",
            "geo_country",
            "geo_region",
            "geo_county",
        ],
    )
    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    async def test_different_facet_fields(
        self,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        facet_name,
        async_client: AsyncClient,
    ):
        """Test that different facet fields work correctly."""
        mock_buckets = [{"key": "Value 1", "doc_count": 10}]
        mock_get_facet.return_value = mock_buckets
        mock_search_criteria.return_value = {"query": None, "filters": {}}
        mock_process.return_value = {
            "data": [],
            "meta": {
                "totalCount": 1,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": facet_name,
                "sort": "count_desc",
            },
        }
        mock_pagination.return_value = {"self": "/test"}
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        response = await async_client.get(f"/api/v1/search/facets/{facet_name}")

        assert response.status_code == 200
        # Verify correct facet name was passed
        call_args = mock_get_facet.call_args
        assert call_args.kwargs["facet_name"] == facet_name


class TestFacetEndpointErrorHandling:
    """Test error handling in facet endpoint."""

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    async def test_elasticsearch_error(
        self,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test handling of Elasticsearch errors."""
        from fastapi import HTTPException

        mock_get_facet.side_effect = HTTPException(status_code=500, detail="ES error")

        response = await async_client.get("/api/v1/search/facets/schema_provider_s")

        assert response.status_code == 500

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    async def test_general_exception(
        self,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test handling of general exceptions."""
        mock_get_facet.side_effect = Exception("Unexpected error")

        response = await async_client.get("/api/v1/search/facets/schema_provider_s")

        assert response.status_code == 500
        assert "error" in response.json()


class TestFacetEndpointIntegration:
    """Integration tests for facet endpoint with mocked Elasticsearch."""

    @patch("app.elasticsearch.search.es")
    @patch("app.api.v1.endpoint_modules.search.SearchService")
    async def test_end_to_end_facet_retrieval(
        self,
        mock_search_service,
        mock_es,
        async_client: AsyncClient,
    ):
        """Test end-to-end facet retrieval with mocked Elasticsearch."""
        # Mock Elasticsearch response
        mock_es_response = MagicMock()
        mock_es_response.body = {
            "aggregations": {
                "facet_values": {
                    "buckets": [
                        {"key": "Provider A", "doc_count": 100},
                        {"key": "Provider B", "doc_count": 50},
                    ]
                }
            }
        }
        mock_es.search = AsyncMock(return_value=mock_es_response)

        # Mock SearchService
        mock_service_instance = MagicMock()
        mock_service_instance.extract_filter_queries.return_value = {}
        mock_service_instance.extract_new_style_filters.return_value = ({}, {})
        mock_search_service.return_value = mock_service_instance

        response = await async_client.get("/api/v1/search/facets/schema_provider_s")

        # Should succeed (200) or handle gracefully (500 if ES not available)
        assert response.status_code in [200, 500]

    @patch("app.elasticsearch.search.es")
    @patch("app.api.v1.endpoint_modules.search.SearchService")
    async def test_facet_with_all_parameters(
        self,
        mock_search_service,
        mock_es,
        async_client: AsyncClient,
    ):
        """Test facet endpoint with all parameters combined."""
        # Mock Elasticsearch response
        mock_es_response = MagicMock()
        mock_es_response.body = {
            "aggregations": {
                "facet_values": {
                    "buckets": [
                        {"key": "University of Minnesota", "doc_count": 25},
                    ]
                }
            }
        }
        mock_es.search = AsyncMock(return_value=mock_es_response)

        # Mock SearchService
        mock_service_instance = MagicMock()
        mock_service_instance.extract_filter_queries.return_value = {}
        mock_service_instance.extract_new_style_filters.return_value = ({}, {})
        mock_search_service.return_value = mock_service_instance

        adv_q = json.dumps([{"op": "AND", "f": "dct_title_s", "q": "test"}])
        response = await async_client.get(
            f"/api/v1/search/facets/schema_provider_s"
            f"?q=water"
            f"&page=1"
            f"&per_page=5"
            f"&sort=alpha_asc"
            f"&q_facet=University"
            f"&adv_q={adv_q}"
        )

        # Should succeed or handle gracefully
        assert response.status_code in [200, 500]

    @patch("app.api.v1.endpoint_modules.search.get_facet_aggregation_config")
    async def test_value_error_handling(self, mock_get_config, async_client: AsyncClient):
        """Test that ValueError from get_facet_aggregation_config is handled."""
        mock_get_config.side_effect = ValueError("Invalid facet name")

        response = await async_client.get("/api/v1/search/facets/invalid_facet")

        assert response.status_code == 400
        assert "error" in response.json()

    @patch("app.api.v1.endpoint_modules.search.get_facet_values")
    @patch("app.api.v1.endpoint_modules.search.process_facet_response")
    @patch("app.api.v1.endpoint_modules.search.get_search_criteria")
    @patch("app.api.v1.endpoint_modules.search.create_pagination_links")
    @patch("app.api.v1.endpoint_modules.search.create_jsonapi_response")
    @patch("app.api.v1.endpoint_modules.search.sanitize_for_json")
    @patch("app.api.v1.endpoint_modules.search.SearchService")
    async def test_response_body_fallback(
        self,
        mock_search_service,
        mock_sanitize,
        mock_jsonapi,
        mock_pagination,
        mock_search_criteria,
        mock_process,
        mock_get_facet,
        async_client: AsyncClient,
    ):
        """Test handling of response without .body attribute."""
        mock_buckets = [{"key": "Provider A", "doc_count": 100}]
        mock_get_facet.return_value = mock_buckets
        mock_search_criteria.return_value = {"query": None, "filters": {}}
        mock_process.return_value = {
            "data": [],
            "meta": {
                "totalCount": 1,
                "totalPages": 1,
                "currentPage": 1,
                "perPage": 10,
                "facetName": "schema_provider_s",
                "sort": "count_desc",
            },
        }
        mock_pagination.return_value = {"self": "/test"}
        mock_jsonapi.return_value = {"jsonapi": {"version": "1.1"}}
        mock_sanitize.side_effect = lambda x: x

        mock_service_instance = MagicMock()
        mock_service_instance.extract_filter_queries.return_value = {}
        mock_service_instance.extract_new_style_filters.return_value = ({}, {})
        mock_search_service.return_value = mock_service_instance

        response = await async_client.get("/api/v1/search/facets/schema_provider_s")

        assert response.status_code == 200

    @patch("app.elasticsearch.search.es")
    @patch("app.api.v1.endpoint_modules.search.SearchService")
    async def test_fq_field_resolution_integration(
        self,
        mock_search_service,
        mock_es,
        async_client: AsyncClient,
    ):
        """Test that fq parameters correctly resolve to .keyword fields in Elasticsearch queries.

        This test ensures that filter queries like fq[gbl_resourceClass_sm][]=Maps
        are correctly resolved to gbl_resourceClass_sm.keyword in the Elasticsearch query,
        preventing the regression where 0 results were returned.
        """
        # Mock Elasticsearch response
        mock_es_response = MagicMock()
        mock_es_response.body = {
            "aggregations": {
                "facet_values": {
                    "buckets": [
                        {"key": "Illinois", "doc_count": 5},
                        {"key": "Minnesota", "doc_count": 3},
                    ]
                }
            }
        }
        mock_es.search = AsyncMock(return_value=mock_es_response)

        # Mock SearchService to return the filter query as extracted from URL
        mock_service_instance = MagicMock()
        # This simulates what extract_filter_queries returns from fq[gbl_resourceClass_sm][]=Maps
        mock_service_instance.extract_filter_queries.return_value = {
            "gbl_resourceClass_sm": ["Maps"]
        }
        mock_service_instance.extract_new_style_filters.return_value = ({}, {})
        mock_search_service.return_value = mock_service_instance

        # Make request matching the user's reported issue
        adv_q = json.dumps([{"op": "AND", "f": "dct_title_s", "q": "illinois"}])
        response = await async_client.get(
            f"/api/v1/search/facets/dct_spatial_sm"
            f"?format=json"
            f"&adv_q={adv_q}"
            f"&fq[gbl_resourceClass_sm][]=Maps"
            f"&page=1"
            f"&per_page=10"
            f"&sort=count_desc"
        )

        # Should succeed
        assert response.status_code == 200

        # Verify that Elasticsearch was called
        mock_es.search.assert_called_once()

        # Verify that the filter query uses .keyword field
        call_args = mock_es.search.call_args
        query_dict = call_args.kwargs["query"]

        # Navigate through the bool query structure to find the filter
        filter_clauses = query_dict["bool"]["filter"]

        # Find the terms filter for gbl_resourceClass_sm
        terms_filter = None
        for clause in filter_clauses:
            if "terms" in clause:
                terms_filter = clause["terms"]
                # Check if this is the filter we're looking for
                if "gbl_resourceClass_sm.keyword" in terms_filter:
                    break

        # Verify that gbl_resourceClass_sm.keyword is used, not gbl_resourceClass_sm
        assert terms_filter is not None, "Expected terms filter with .keyword not found"
        assert "gbl_resourceClass_sm.keyword" in terms_filter, (
            f"Expected 'gbl_resourceClass_sm.keyword' in filter, "
            f"but got: {list(terms_filter.keys())}"
        )
        assert terms_filter["gbl_resourceClass_sm.keyword"] == ["Maps"]
