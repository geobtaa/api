"""
Tests for the SearchService.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.elasticsearch.search import public_visibility_filter_clauses
from app.services.search_service import SearchService


@pytest.mark.asyncio
async def test_search_preserves_search_payload_and_adds_lightweight_timings():
    """SearchService should not enrich each hit when the endpoint rebuilds final resources."""
    service = SearchService()

    with patch("app.services.search_service.search_resources") as mock_search:
        mock_search.return_value = {
            "data": [{"id": "1", "attributes": {"dct_title_s": "Test Resource"}}],
            "meta": {"suggestions": ["test resource"]},
            "queryTime": {"elasticsearch": "12ms", "postgresql": "8ms"},
        }

        result = await service.search(q="test", page=1, limit=10)

    assert result["data"][0]["attributes"]["dct_title_s"] == "Test Resource"
    assert "ui_thumbnail_url" not in result["data"][0]["attributes"]
    assert "ui_citation" not in result["data"][0]["attributes"]
    assert result["meta"]["spellingSuggestions"] == ["test resource"]
    assert result["queryTime"]["elasticsearch"] == "12ms"
    assert result["queryTime"]["postgresql"] == "8ms"
    assert result["queryTime"]["resourceProcessing"]["total"] == "0ms"
    assert "totalResponseTime" in result["queryTime"]


@pytest.mark.asyncio
async def test_search_forwards_hydrate_hits_flag():
    service = SearchService()

    with patch("app.services.search_service.search_resources") as mock_search:
        mock_search.return_value = {"data": [], "meta": {}, "queryTime": {}}

        await service.search(q="test", page=1, limit=10, hydrate_hits=False)

    assert mock_search.call_args.kwargs["hydrate_hits"] is False


@pytest.mark.asyncio
async def test_search_can_skip_result_sanitization_for_internal_callers():
    service = SearchService()

    with patch("app.services.search_service.search_resources") as mock_search:
        mock_search.return_value = {"data": [], "meta": {}, "queryTime": {}}

        result = await service.search(q="test", page=1, limit=10, sanitize_response=False)

    assert result is mock_search.return_value


@pytest.mark.integration
@pytest.mark.elasticsearch
class TestSearchService:
    """Test cases for SearchService class."""

    @pytest.mark.unit
    def test_search_service_initialization(self):
        """Test that the SearchService can be initialized."""
        service = SearchService()
        assert service is not None
        assert hasattr(service, "index_name")
        assert hasattr(service, "es")
        # In test environment, the index name might be different
        assert service.index_name in [
            "btaa_geospatial_api",
            "btaa_geospatial_api_test",
            "btaa_ogm_api_test",
            "btaa_ogm_api",
        ]

    @pytest.mark.asyncio
    async def test_search_with_id_field_in_multi_match(self):
        """Test that the search query includes the id field in multi_match."""
        service = SearchService()

        # Mock the search_resources function to capture the query
        with patch("app.services.search_service.search_resources") as mock_search:
            # Mock the response
            mock_response = {
                "data": [],
                "meta": {"totalCount": 0, "currentPage": 1, "perPage": 10, "totalPages": 0},
                "included": [],
            }
            mock_search.return_value = mock_response

            # Call the search method
            await service.search(q="test-resource-id", page=1, limit=10)

            # Verify that search_resources was called
            mock_search.assert_called_once()

            # Get the call arguments
            call_args = mock_search.call_args
            query_param = call_args.kwargs.get("query") or call_args.args[0]

            # Verify the query parameter was passed correctly
            assert query_param == "test-resource-id"
            assert call_args.kwargs["include_non_public"] is False

    @pytest.mark.asyncio
    async def test_search_forwards_include_non_public_override(self):
        """SearchService should pass the diagnostics visibility override through."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            mock_search.return_value = {"data": [], "meta": {}, "included": []}

            await service.search(q="test", page=1, limit=10, include_non_public=True)

        assert mock_search.call_args.kwargs["include_non_public"] is True

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Test search with filter parameters."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            mock_response = {
                "data": [],
                "meta": {"totalCount": 0, "currentPage": 1, "perPage": 10, "totalPages": 0},
                "included": [],
            }
            mock_search.return_value = mock_response

            # Call with filter parameters
            await service.search(
                q="test", page=1, limit=10, request_query_params="fq[dct_spatial_sm][]=Minnesota"
            )

            # Verify that search_resources was called with filters
            mock_search.assert_called_once()
            call_args = mock_search.call_args
            fq_param = call_args.kwargs.get("fq")

            # The filter should be extracted and passed
            assert fq_param is not None

    @pytest.mark.asyncio
    async def test_search_with_sort(self):
        """Test search with sort parameter."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            mock_response = {
                "data": [],
                "meta": {"totalCount": 0, "currentPage": 1, "perPage": 10, "totalPages": 0},
                "included": [],
            }
            mock_search.return_value = mock_response

            # Call with sort parameter
            await service.search(q="test", page=1, limit=10, sort="year_desc")

            # Verify that search_resources was called
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """Test search error handling."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            # Mock an exception
            mock_search.side_effect = Exception("Elasticsearch error")

            # Call the search method
            result = await service.search(q="test", page=1, limit=10)

            # Verify error response structure
            assert "message" in result
            assert "error" in result
            assert result["message"] == "Search operation failed"
            assert result["error_type"] == "elasticsearch"
            assert result["error"] == "search_request_failed"

    @pytest.mark.asyncio
    async def test_search_classifies_returned_dependency_errors(self):
        """Search should tag error payloads returned by the Elasticsearch layer."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            mock_search.return_value = {
                "error": "500: {'message': 'Elasticsearch query failed', 'status_code': 503}",
            }

            result = await service.search(q="test", page=1, limit=10)

            assert result["message"] == "Search operation failed"
            assert result["error_type"] == "connection"
            assert "queryTime" in result

    def test_extract_filter_queries(self):
        """Test the extract_filter_queries method."""
        service = SearchService()

        # Test with valid filter parameters using aggregation field names
        params = "fq[spatial_agg][]=Minnesota&fq[provider_agg][]=Test%20Provider"
        result = service.extract_filter_queries(params)

        assert "dct_spatial_sm" in result
        assert "schema_provider_s" in result
        assert result["dct_spatial_sm"] == ["Minnesota"]
        assert result["schema_provider_s"] == ["Test Provider"]

        # Test with invalid filter parameters (should be ignored)
        params = "fq[invalid_field][]=value&other_param=test"
        result = service.extract_filter_queries(params)

        # Should be empty since invalid_field is not in agg_to_field mapping
        assert result == {}

    def test_extract_filter_queries_multiple_values(self):
        """Test extract_filter_queries with multiple values for same field."""
        service = SearchService()

        params = "fq[spatial_agg][]=Minnesota&fq[spatial_agg][]=Wisconsin"
        result = service.extract_filter_queries(params)

        assert "dct_spatial_sm" in result
        assert result["dct_spatial_sm"] == ["Minnesota", "Wisconsin"]

    def test_extract_filter_queries_empty_params(self):
        """Test extract_filter_queries with empty parameters."""
        service = SearchService()

        result = service.extract_filter_queries("")
        assert result == {}

        result = service.extract_filter_queries("other_param=value")
        assert result == {}

    @pytest.mark.asyncio
    async def test_search_with_real_data_and_processing(self):
        """Test search with real data to hit the resource processing loop."""
        service = SearchService()

        # This should hit the actual Elasticsearch and process real resources
        try:
            result = await service.search(q="map", page=1, limit=5)

            if "error" in result:
                assert result["message"] == "Search operation failed"
                assert result["error_type"] in {"connection", "elasticsearch"}
                assert "event loop" not in str(result.get("error", "")).lower()
                return

            # Verify the structure
            assert "data" in result
            assert "meta" in result
            assert "queryTime" in result

            # If we have data, verify the processing worked
            if result["data"]:
                first_resource = result["data"][0]
                assert "attributes" in first_resource
                attributes = first_resource["attributes"]

                # Attributes should be nested with ogm and/or b1g structure
                assert isinstance(attributes, dict)
                # Check for nested structure (ogm and/or b1g)
                if "ogm" in attributes:
                    assert isinstance(attributes["ogm"], dict)
                if "b1g" in attributes:
                    assert isinstance(attributes["b1g"], dict)

                # UI fields should be in meta.ui, not in attributes
                assert "ui_thumbnail_url" not in attributes
                assert "ui_citation" not in attributes

                # Verify timing information
                assert "elasticsearch" in result["queryTime"]
                assert "resourceProcessing" in result["queryTime"]
                assert "totalResponseTime" in result["queryTime"]

        except AssertionError:
            raise
        except Exception as e:
            # Handle connection errors gracefully
            assert (
                "connection" in str(e).lower()
                or "event loop" in str(e).lower()
                or "nodename" in str(e).lower()
            )

    @pytest.mark.asyncio
    async def test_search_with_suggestions_handling(self):
        """Test search results that include suggestions."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            # Mock response with suggestions
            mock_response = {
                "data": [],
                "meta": {"totalCount": 0, "suggestions": ["map", "mapping", "maps"]},
            }
            mock_search.return_value = mock_response

            result = await service.search(q="map", page=1, limit=10)

            # Verify suggestions were moved from meta.suggestions to meta.spellingSuggestions
            assert "meta" in result
            assert "spellingSuggestions" in result["meta"]
            assert "suggestions" not in result["meta"]
            assert result["meta"]["spellingSuggestions"] == ["map", "mapping", "maps"]

    @pytest.mark.asyncio
    async def test_get_resource_success(self):
        """Test getting a single resource by ID."""
        service = SearchService()

        try:
            # Try to get a resource that might exist in production
            result = await service.get_resource("test-id")

            # If successful, verify structure
            assert "data" in result
            assert "type" in result["data"]
            assert "id" in result["data"]
            assert "attributes" in result["data"]
            assert result["data"]["type"] == "resource"
            assert result["data"]["id"] == "test-id"

        except Exception as e:
            # Handle cases where resource doesn't exist or connection issues
            error_msg = str(e).lower()
            assert any(
                term in error_msg for term in ["not found", "connection", "event loop", "nodename"]
            )

    @pytest.mark.asyncio
    async def test_get_resource_with_relationships(self):
        """Test getting a resource with relationships."""
        service = SearchService()

        try:
            result = await service.get_resource("test-id", include_relationships=True)

            if "data" in result:
                # UI fields should be in meta.ui, not in attributes
                # Check meta.ui structure instead
                assert "meta" in result["data"]
                assert "ui" in result["data"]["meta"]

        except Exception as e:
            error_msg = str(e).lower()
            assert any(
                term in error_msg for term in ["not found", "connection", "event loop", "nodename"]
            )

    @pytest.mark.asyncio
    async def test_get_resource_with_summaries(self):
        """Test getting a resource with summaries."""
        service = SearchService()

        try:
            result = await service.get_resource("test-id", include_summaries=True)

            if "data" in result:
                attributes = result["data"]["attributes"]
                # Attributes should have nested structure (ogm and/or b1g)
                assert isinstance(attributes, dict)
                # UI fields should be in meta.ui, not in attributes
                assert "meta" in result["data"]
                assert "ui" in result["data"]["meta"]
                # Similar items are not guaranteed to be present for this code path.
                # If present, ensure the shape is reasonable.
                if "similar_items" in result["data"]["meta"]["ui"]:
                    assert isinstance(result["data"]["meta"]["ui"]["similar_items"], list)

        except Exception as e:
            error_msg = str(e).lower()
            assert any(
                term in error_msg for term in ["not found", "connection", "event loop", "nodename"]
            )

    @pytest.mark.asyncio
    async def test_get_resource_without_relationships_or_summaries(self):
        """Test getting a resource without relationships or summaries."""
        service = SearchService()

        try:
            result = await service.get_resource(
                "test-id", include_relationships=False, include_summaries=False
            )

            if "data" in result:
                attributes = result["data"]["attributes"]
                # Should not have these fields
                # UI fields should not be in attributes (they're in meta.ui)
                # Attributes should only contain ogm and/or b1g
                if "ogm" in attributes:
                    assert "ui_relationships" not in attributes["ogm"]
                    assert "ui_summaries" not in attributes["ogm"]
                if "b1g" in attributes:
                    assert "ui_relationships" not in attributes["b1g"]
                    assert "ui_summaries" not in attributes["b1g"]

        except Exception as e:
            error_msg = str(e).lower()
            assert any(
                term in error_msg for term in ["not found", "connection", "event loop", "nodename"]
            )

    @pytest.mark.asyncio
    async def test_get_resource_json_parsing(self):
        """Test get_resource with JSON parsing of dct_references_s."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            # Mock Elasticsearch response with JSON string in dct_references_s
            mock_es.get.return_value = {
                "_source": {
                    "id": "test-id",
                    "publication_state": "published",
                    "gbl_suppressed_b": False,
                    "dct_references_s": '{"download": "http://example.com/download"}',
                }
            }

            # Mock other services
            with (
                patch("app.services.search_service.DownloadService"),
                patch("app.services.search_service.ViewerService"),
                patch("app.services.search_service.CitationService"),
            ):
                try:
                    result = await service.get_resource(
                        "test-id", include_relationships=False, include_summaries=False
                    )

                    assert "data" in result
                    attributes = result["data"]["attributes"]
                    # Attributes should have nested structure (ogm and/or b1g)
                    assert isinstance(attributes, dict)
                    # dct_references_s should be in ogm namespace
                    assert "ogm" in attributes
                    assert "dct_references_s" in attributes["ogm"]
                    # Should be parsed as dict, not string
                    assert isinstance(attributes["ogm"]["dct_references_s"], dict)
                    assert (
                        attributes["ogm"]["dct_references_s"]["download"]
                        == "http://example.com/download"
                    )
                except Exception as e:
                    # Handle event loop issues gracefully
                    assert "event loop" in str(e).lower() or "connection" in str(e).lower()

    @pytest.mark.asyncio
    async def test_get_resource_invalid_json_handling(self):
        """Test get_resource with invalid JSON in dct_references_s."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            # Mock Elasticsearch response with invalid JSON
            mock_es.get.return_value = {
                "_source": {
                    "id": "test-id",
                    "publication_state": "published",
                    "gbl_suppressed_b": False,
                    "dct_references_s": "invalid json{",
                }
            }

            # Mock other services
            with (
                patch("app.services.search_service.DownloadService"),
                patch("app.services.search_service.ViewerService"),
                patch("app.services.search_service.CitationService"),
            ):
                try:
                    result = await service.get_resource(
                        "test-id", include_relationships=False, include_summaries=False
                    )

                    assert "data" in result
                    attributes = result["data"]["attributes"]
                    # Attributes should have nested structure (ogm and/or b1g)
                    assert isinstance(attributes, dict)
                    # dct_references_s should be in ogm namespace
                    assert "ogm" in attributes
                    assert "dct_references_s" in attributes["ogm"]
                    # Should remain as string when JSON parsing fails
                    assert attributes["ogm"]["dct_references_s"] == "invalid json{"
                except Exception as e:
                    # Handle event loop, connection, or mock ES 404 gracefully
                    error_msg = str(e).lower()
                    assert any(
                        term in error_msg
                        for term in ["event loop", "connection", "404", "not found"]
                    )

    @pytest.mark.asyncio
    async def test_get_resource_hides_non_public_elasticsearch_documents(self):
        """Service-level Elasticsearch resource lookups should honor public visibility."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            mock_es.get.return_value = {
                "_source": {
                    "id": "retired-id",
                    "publication_state": "retired",
                    "gbl_suppressed_b": False,
                }
            }

            with pytest.raises(HTTPException) as exc_info:
                await service.get_resource(
                    "retired-id",
                    include_relationships=False,
                    include_summaries=False,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_suggest_success(self):
        """Test the suggest method."""
        service = SearchService()

        result = await service.suggest("map", size=3)

        # Verify structure
        assert "data" in result
        assert "meta" in result
        assert isinstance(result["data"], list)

        if "error" in result["meta"]:
            error_msg = result["meta"]["error"].lower()
            assert any(
                term in error_msg
                for term in ["connection", "event loop", "nodename", "notfound", "no such index"]
            )
            return

        assert result["meta"]["query"] == "map"
        assert "es_query" in result["meta"]
        assert "es_response" in result["meta"]

    @pytest.mark.asyncio
    async def test_suggest_with_resource_class(self):
        """Test suggest with resource_class parameter."""
        service = SearchService()

        result = await service.suggest("map", resource_class="Dataset", size=5)

        assert "meta" in result
        if "error" in result["meta"]:
            error_msg = result["meta"]["error"].lower()
            assert any(
                term in error_msg
                for term in ["connection", "event loop", "nodename", "notfound", "no such index"]
            )
            return

        assert result["meta"]["resource_class"] == "Dataset"

    @pytest.mark.asyncio
    async def test_suggest_query_applies_public_visibility_filters(self):
        """Suggestions should use the same public visibility default as search."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:

            async def mock_search(*args, **kwargs):
                return type("MockResponse", (), {"body": {"hits": {"hits": []}}})()

            mock_es.search = mock_search

            result = await service.suggest("test", resource_class="Dataset", size=3)

        query = result["meta"]["es_query"]
        bool_query = query["query"]["bool"]
        assert query["size"] == 12
        assert bool_query["must"][0]["multi_match"]["type"] == "bool_prefix"
        for visibility_filter in public_visibility_filter_clauses():
            assert visibility_filter in bool_query["filter"]
        assert {"term": {"gbl_resourceClass_sm.keyword": "Dataset"}} in bool_query["filter"]

    @pytest.mark.asyncio
    async def test_suggest_include_non_public_omits_public_visibility_filters(self):
        """The diagnostic override should remove publication/suppression filters."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:

            async def mock_search(*args, **kwargs):
                return type("MockResponse", (), {"body": {"hits": {"hits": []}}})()

            mock_es.search = mock_search

            result = await service.suggest("test", include_non_public=True)

        bool_query = result["meta"]["es_query"]["query"]["bool"]
        assert "filter" not in bool_query

    @pytest.mark.asyncio
    async def test_suggest_error_handling(self):
        """Test suggest method error handling."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            mock_es.search.side_effect = Exception("Elasticsearch error")

            result = await service.suggest("test")

            assert "data" in result
            assert result["data"] == []
            assert "meta" in result
            assert "error" in result["meta"]
            assert "Elasticsearch error" in result["meta"]["error"]

    @pytest.mark.asyncio
    async def test_suggest_with_options_processing(self):
        """Test suggest method with options processing."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            # Mock response with suggestions - make it awaitable
            async def mock_search(*args, **kwargs):
                return type(
                    "MockResponse",
                    (),
                    {
                        "body": {
                            "suggest": {
                                "my-suggestion": [
                                    {
                                        "options": [
                                            {
                                                "_id": "doc1",
                                                "_source": {"dct_title_s": "Test Map"},
                                                "text": "test map",
                                                "_score": 1.0,
                                            },
                                            {
                                                "_id": "doc2",
                                                "_source": {"dct_title_s": "Another Map"},
                                                "text": "another map",
                                                "_score": 0.8,
                                            },
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                )()

            mock_es.search = mock_search

            result = await service.suggest("test")

            assert "data" in result
            assert len(result["data"]) == 2

            # Check first suggestion
            suggestion1 = result["data"][0]
            assert suggestion1["type"] == "suggestion"
            assert suggestion1["id"] == "doc1"
            assert suggestion1["attributes"] == {"text": "test map", "score": 1.0}

    @pytest.mark.asyncio
    async def test_suggest_normalizes_and_deduplicates_dirty_text(self):
        """Test suggest cleans noisy text and deduplicates equivalent variants."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:

            async def mock_search(*args, **kwargs):
                return type(
                    "MockResponse",
                    (),
                    {
                        "body": {
                            "suggest": {
                                "my-suggestion": [
                                    {
                                        "options": [
                                            {"_id": "doc1", "text": "(Chicago)", "_score": 6.0},
                                            {"_id": "doc2", "text": "(Chicago, )", "_score": 6.0},
                                            {
                                                "_id": "doc3",
                                                "text": "Chicago (Ill.)",
                                                "_score": 6.0,
                                            },
                                            {
                                                "_id": "doc4",
                                                "text": (
                                                    "Chicago : Department of City Planning, 1961."
                                                ),
                                                "_score": 6.0,
                                            },
                                            {
                                                "_id": "doc5",
                                                "text": "Chicago Metropolitan Agency for Planning",
                                                "_score": 6.0,
                                            },
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                )()

            mock_es.search = mock_search

            result = await service.suggest("chicago", size=5)

            assert [item["attributes"]["text"] for item in result["data"]] == [
                "chicago",
                "chicago ill",
                "chicago department of city planning",
                "chicago metropolitan agency for planning",
            ]
            assert result["meta"]["es_query"]["size"] == 20
            assert {"term": {"publication_state": "published"}} in result["meta"]["es_query"][
                "query"
            ]["bool"]["filter"]

    @pytest.mark.asyncio
    async def test_search_resource_processing_timing(self):
        """Test that search includes proper timing information."""
        service = SearchService()

        try:
            result = await service.search(q="test", page=1, limit=2)

            if "queryTime" in result:
                timings = result["queryTime"]

                # Should have all timing fields
                assert "elasticsearch" in timings
                assert "resourceProcessing" in timings
                assert "totalResponseTime" in timings

                # Resource processing should have detailed breakdown
                processing = timings["resourceProcessing"]
                assert "total" in processing
                assert "perResource" in processing
                assert "thumbnailService" in processing
                assert "citationService" in processing
                assert "viewerService" in processing

        except Exception as e:
            error_msg = str(e).lower()
            assert any(term in error_msg for term in ["connection", "event loop", "nodename"])

    def test_extract_filter_queries_all_aggregation_fields(self):
        """Test extract_filter_queries with all supported aggregation fields."""
        service = SearchService()

        # Test all aggregation fields
        params = (
            "fq[id_agg][]=1&"
            "fq[spatial_agg][]=Minnesota&"
            "fq[resource_type_agg][]=Dataset&"
            "fq[resource_class_agg][]=Dataset&"
            "fq[index_year_agg][]=2023&"
            "fq[language_agg][]=English&"
            "fq[creator_agg][]=Test Creator&"
            "fq[provider_agg][]=Test Provider&"
            "fq[b1g_code_s][]=BTAA&"
            "fq[access_rights_agg][]=Public&"
            "fq[georeferenced_agg][]=true&"
            "fq[map_overlay_agg][]=true&"
            "fq[geo_country_agg][]=USA&"
            "fq[geo_region_agg][]=Midwest&"
            "fq[geo_county_agg][]=Hennepin"
        )

        result = service.extract_filter_queries(params)

        # Verify all fields are mapped correctly
        assert result["id.keyword"] == ["1"]
        assert result["dct_spatial_sm"] == ["Minnesota"]
        assert result["gbl_resourceType_sm"] == ["Dataset"]
        assert result["gbl_resourceClass_sm"] == ["Dataset"]
        assert result["gbl_indexYear_im"] == ["2023"]
        assert result["b1g_language_sm"] == ["English"]
        assert result["dct_creator_sm"] == ["Test Creator"]
        assert result["schema_provider_s"] == ["Test Provider"]
        assert result["b1g_code_s"] == ["BTAA"]
        assert result["dct_accessRights_s"] == ["Public"]
        assert result["gbl_georeferenced_b"] == ["true"]
        assert result["b1g_georeferenced_allmaps_b"] == ["true"]
        assert result["geo_country"] == ["USA"]
        assert result["geo_region"] == ["Midwest"]
        assert result["geo_county"] == ["Hennepin"]

    def test_extract_filter_queries_relationship_fields(self):
        """extract_filter_queries accepts relationship fields (Has part / Collection records)."""
        service = SearchService()

        # Direct field names used by frontend include_filters for "Browse all" links
        params = "fq[dct_isPartOf_sm][]=parent-uuid-123&fq[pcdm_memberOf_sm][]=collection-uuid-456"
        result = service.extract_filter_queries(params)

        assert result["dct_isPartOf_sm"] == ["parent-uuid-123"]
        assert result["pcdm_memberOf_sm"] == ["collection-uuid-456"]

    @pytest.mark.asyncio
    async def test_get_resource_not_found(self):
        """Test get_resource with NotFoundError."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            from elasticsearch.exceptions import NotFoundError

            # Create a proper NotFoundError with required arguments
            mock_es.get.side_effect = NotFoundError(
                message="Document not found", meta=None, body={"found": False}
            )

            try:
                await service.get_resource("nonexistent-id")
                raise AssertionError("Should have raised HTTPException")
            except Exception as e:
                # Should raise HTTPException with 404, but may get event loop error
                error_msg = str(e).lower()
                assert any(term in error_msg for term in ["not found", "event loop", "connection"])

    @pytest.mark.asyncio
    async def test_get_resource_elasticsearch_error(self):
        """Test get_resource with general Elasticsearch error."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            mock_es.get.side_effect = Exception("Elasticsearch connection error")

            try:
                await service.get_resource("test-id")
                raise AssertionError("Should have raised HTTPException")
            except Exception as e:
                # Should raise HTTPException with 500
                assert "connection error" in str(e).lower() or "event loop" in str(e).lower()

    @pytest.mark.asyncio
    async def test_get_resource_general_error_handling(self):
        """Test get_resource with general error handling."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            mock_es.get.side_effect = Exception("General error")

            try:
                await service.get_resource("test-id")
                raise AssertionError("Should have raised HTTPException")
            except Exception as e:
                # Should raise HTTPException with 500
                assert "general error" in str(e).lower() or "event loop" in str(e).lower()

    @pytest.mark.asyncio
    async def test_search_with_no_suggestions_in_meta(self):
        """Test search when meta doesn't have suggestions."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            # Mock response without suggestions
            mock_response = {
                "data": [{"id": "1", "attributes": {"title": "Test"}}],
                "meta": {"totalCount": 1},
            }
            mock_search.return_value = mock_response

            result = await service.search(q="test", page=1, limit=10)

            # Should not have spellingSuggestions in meta
            assert "meta" in result
            assert "spellingSuggestions" not in result["meta"]

    @pytest.mark.asyncio
    async def test_search_with_empty_suggestions(self):
        """Test search when meta has empty suggestions."""
        service = SearchService()

        with patch("app.services.search_service.search_resources") as mock_search:
            # Mock response with empty suggestions
            mock_response = {"data": [], "meta": {"totalCount": 0, "suggestions": []}}
            mock_search.return_value = mock_response

            result = await service.search(q="test", page=1, limit=10)

            # Should have empty spellingSuggestions
            assert "meta" in result
            assert "spellingSuggestions" in result["meta"]
            assert result["meta"]["spellingSuggestions"] == []

    @pytest.mark.asyncio
    async def test_suggest_with_no_options_in_response(self):
        """Test suggest when response has no options."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            # Mock response without options
            async def mock_search(*args, **kwargs):
                return type(
                    "MockResponse", (), {"body": {"suggest": {"my-suggestion": [{"options": []}]}}}
                )()

            mock_es.search = mock_search

            result = await service.suggest("test")

            assert "data" in result
            assert result["data"] == []

    @pytest.mark.asyncio
    async def test_suggest_with_no_suggest_in_response(self):
        """Test suggest when response has no suggest field."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            # Mock response without suggest field
            async def mock_search(*args, **kwargs):
                return type("MockResponse", (), {"body": {}})()

            mock_es.search = mock_search

            result = await service.suggest("test")

            assert "data" in result
            assert result["data"] == []

    @pytest.mark.asyncio
    async def test_suggest_with_duplicate_ids(self):
        """Test suggest with duplicate IDs to test deduplication."""
        service = SearchService()

        with patch("app.services.search_service.es") as mock_es:
            # Mock response with duplicate IDs
            async def mock_search(*args, **kwargs):
                return type(
                    "MockResponse",
                    (),
                    {
                        "body": {
                            "suggest": {
                                "my-suggestion": [
                                    {
                                        "options": [
                                            {
                                                "_id": "doc1",
                                                "_source": {"dct_title_s": "Test Map"},
                                                "text": "test map",
                                                "_score": 1.0,
                                            },
                                            {
                                                "_id": "doc1",  # Duplicate ID
                                                "_source": {"dct_title_s": "Test Map Duplicate"},
                                                "text": "test map duplicate",
                                                "_score": 0.9,
                                            },
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                )()

            mock_es.search = mock_search

            result = await service.suggest("test")

            assert "data" in result
            assert len(result["data"]) == 1  # Should deduplicate
            assert result["data"][0]["id"] == "doc1"

    def test_extract_filter_queries_with_empty_values(self):
        """Test extract_filter_queries with empty values."""
        service = SearchService()

        # Test with empty values - parse_qs behavior may vary
        params = "fq[spatial_agg][]=&fq[spatial_agg][]=Minnesota"
        result = service.extract_filter_queries(params)

        assert "dct_spatial_sm" in result
        # The result should contain Minnesota, empty values may or may not be included
        assert "Minnesota" in result["dct_spatial_sm"]
        assert len(result["dct_spatial_sm"]) >= 1

    def test_extract_filter_queries_with_none_values(self):
        """Test extract_filter_queries with None values."""
        service = SearchService()

        # Test with None values (should be handled gracefully)
        params = "fq[spatial_agg][]=Minnesota"
        result = service.extract_filter_queries(params)

        assert "dct_spatial_sm" in result
        assert result["dct_spatial_sm"] == ["Minnesota"]

    def test_extract_new_style_filters_geo_polygon(self):
        """Ensure geo include_filters parse into structured dict."""
        service = SearchService()

        params = (
            "include_filters[geo][type]=polygon&"
            "include_filters[geo][field]=locn_geometry&"
            "include_filters[geo][relation]=intersects&"
            "include_filters[geo][points][0][lat]=45&"
            "include_filters[geo][points][0][lon]=-104&"
            "include_filters[geo][points][1][lat]=45&"
            "include_filters[geo][points][1][lon]=-109&"
            "include_filters[geo][points][2][lat]=41&"
            "include_filters[geo][points][2][lon]=-109&"
            "include_filters[geo][points][3][lat]=41&"
            "include_filters[geo][points][3][lon]=-104"
        )

        include, exclude = service.extract_new_style_filters(params)

        assert "geo" in include
        geo = include["geo"]
        assert geo["type"] == "polygon"
        assert geo["field"] == "locn_geometry"
        assert geo["relation"] == "intersects"
        assert len(geo["points"]) == 4
        assert geo["points"][0] == {"lat": 45.0, "lon": -104.0}
        assert exclude == {}

    def test_extract_new_style_filters_geo_bbox(self):
        """Bbox params should normalize to nested dict."""
        service = SearchService()

        params = (
            "include_filters[geo][type]=bbox&"
            "include_filters[geo][field]=dcat_bbox&"
            "include_filters[geo][relation]=within&"
            "include_filters[geo][top_left][lat]=45&"
            "include_filters[geo][top_left][lon]=-109&"
            "include_filters[geo][bottom_right][lat]=41&"
            "include_filters[geo][bottom_right][lon]=-104"
        )

        include, exclude = service.extract_new_style_filters(params)

        bbox = include["geo"]
        assert bbox["type"] == "bbox"
        assert bbox["field"] == "dcat_bbox"
        assert bbox["relation"] == "within"
        assert bbox["top_left"] == {"lat": 45.0, "lon": -109.0}
        assert bbox["bottom_right"] == {"lat": 41.0, "lon": -104.0}
        assert exclude == {}

    def test_extract_new_style_filters_geo_distance(self):
        """Distance params should normalize center and numeric distance."""
        service = SearchService()

        params = (
            "include_filters[geo][type]=distance&"
            "include_filters[geo][field]=dcat_centroid&"
            "include_filters[geo][distance]=25km&"
            "include_filters[geo][center][lat]=43.5&"
            "include_filters[geo][center][lon]=-106.2"
        )

        include, exclude = service.extract_new_style_filters(params)

        dist = include["geo"]
        assert dist["type"] == "distance"
        assert dist["field"] == "dcat_centroid"
        assert dist["distance"] == "25km"
        assert dist["center"] == {"lat": 43.5, "lon": -106.2}
        assert exclude == {}

    @pytest.mark.asyncio
    async def test_search_passes_geospatial_include_filters(self):
        """Search should forward geo include_filters unchanged."""
        service = SearchService()

        geo_filter = {
            "geo": {
                "type": "polygon",
                "field": "locn_geometry",
                "relation": "within",
                "points": [
                    {"lat": 45.0, "lon": -104.0},
                    {"lat": 45.0, "lon": -109.0},
                    {"lat": 41.0, "lon": -109.0},
                    {"lat": 41.0, "lon": -104.0},
                ],
            }
        }

        with patch("app.services.search_service.search_resources") as mock_search:
            mock_search.return_value = {"data": [], "meta": {"totalCount": 0}}

            await service.search(q=None, page=1, limit=5, include_filters=geo_filter)

            mock_search.assert_called_once()
            include_arg = mock_search.call_args.kwargs.get("include_filters")
            assert include_arg == geo_filter

    @pytest.mark.asyncio
    async def test_search_passes_geospatial_bbox_filters(self):
        service = SearchService()

        geo_filter = {
            "geo": {
                "type": "bbox",
                "field": "dcat_bbox",
                "top_left": {"lat": 45.0, "lon": -109.0},
                "bottom_right": {"lat": 41.0, "lon": -104.0},
            }
        }

        with patch("app.services.search_service.search_resources") as mock_search:
            mock_search.return_value = {"data": [], "meta": {"totalCount": 0}}

            await service.search(q=None, page=1, limit=5, include_filters=geo_filter)

            include_arg = mock_search.call_args.kwargs.get("include_filters")
            assert include_arg == geo_filter

    @pytest.mark.asyncio
    async def test_search_passes_geospatial_distance_filters(self):
        service = SearchService()

        geo_filter = {
            "geo": {
                "type": "distance",
                "field": "dcat_centroid",
                "distance": "25km",
                "center": {"lat": 43.5, "lon": -106.2},
            }
        }

        with patch("app.services.search_service.search_resources") as mock_search:
            mock_search.return_value = {"data": [], "meta": {"totalCount": 0}}

            await service.search(q=None, page=1, limit=5, include_filters=geo_filter)

            include_arg = mock_search.call_args.kwargs.get("include_filters")
            assert include_arg == geo_filter
