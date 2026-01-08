"""
Tests for facet-related functions in app.elasticsearch.search module.

Tests cover:
- get_facet_aggregation_config
- get_facet_values
- process_facet_response
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.elasticsearch.search import (
    get_facet_aggregation_config,
    get_facet_values,
    process_facet_response,
)


class TestGetFacetAggregationConfig:
    """Test get_facet_aggregation_config function."""

    def test_valid_facet_names(self):
        """Test that valid facet names return correct configuration."""
        valid_facets = [
            "dct_spatial_sm",
            "gbl_resourceClass_sm",
            "gbl_resourceType_sm",
            "gbl_indexYear_im",
            "dct_language_sm",
            "dct_creator_sm",
            "schema_provider_s",
            "dct_accessRights_s",
            "gbl_georeferenced_b",
            "geo_country",
            "geo_region",
            "geo_county",
        ]

        for facet_name in valid_facets:
            config = get_facet_aggregation_config(facet_name)
            assert "field" in config
            assert "size" in config
            assert isinstance(config["field"], str)
            assert isinstance(config["size"], int)

    def test_invalid_facet_name(self):
        """Test that invalid facet name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid facet name"):
            get_facet_aggregation_config("invalid_facet")

    def test_keyword_fields(self):
        """Test that keyword fields are correctly configured."""
        config = get_facet_aggregation_config("dct_spatial_sm")
        assert config["field"] == "dct_spatial_sm.keyword"

        config = get_facet_aggregation_config("schema_provider_s")
        assert config["field"] == "schema_provider_s.keyword"

    def test_non_keyword_fields(self):
        """Test that non-keyword fields are correctly configured."""
        config = get_facet_aggregation_config("gbl_indexYear_im")
        assert config["field"] == "gbl_indexYear_im"
        assert ".keyword" not in config["field"]

        config = get_facet_aggregation_config("gbl_georeferenced_b")
        assert config["field"] == "gbl_georeferenced_b"
        assert ".keyword" not in config["field"]


class TestProcessFacetResponse:
    """Test process_facet_response function."""

    def test_basic_processing(self):
        """Test basic facet response processing."""
        buckets = [
            {"key": "Provider A", "doc_count": 100},
            {"key": "Provider B", "doc_count": 50},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
        )

        assert "data" in result
        assert "meta" in result
        assert len(result["data"]) == 2
        assert result["meta"]["totalCount"] == 2
        assert result["meta"]["facetName"] == "schema_provider_s"

    def test_sort_count_desc(self):
        """Test sorting by count descending."""
        buckets = [
            {"key": "Provider B", "doc_count": 50},
            {"key": "Provider A", "doc_count": 100},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            sort="count_desc",
        )

        # Should be sorted by count descending
        assert result["data"][0]["attributes"]["hits"] == 100
        assert result["data"][1]["attributes"]["hits"] == 50

    def test_sort_count_asc(self):
        """Test sorting by count ascending."""
        buckets = [
            {"key": "Provider A", "doc_count": 100},
            {"key": "Provider B", "doc_count": 50},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            sort="count_asc",
        )

        # Should be sorted by count ascending
        assert result["data"][0]["attributes"]["hits"] == 50
        assert result["data"][1]["attributes"]["hits"] == 100

    def test_sort_alpha_asc(self):
        """Test sorting alphabetically ascending."""
        buckets = [
            {"key": "Provider B", "doc_count": 50},
            {"key": "Provider A", "doc_count": 100},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            sort="alpha_asc",
        )

        # Should be sorted alphabetically
        assert result["data"][0]["attributes"]["value"] == "Provider A"
        assert result["data"][1]["attributes"]["value"] == "Provider B"

    def test_sort_alpha_desc(self):
        """Test sorting alphabetically descending."""
        buckets = [
            {"key": "Provider A", "doc_count": 100},
            {"key": "Provider B", "doc_count": 50},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            sort="alpha_desc",
        )

        # Should be sorted alphabetically descending
        assert result["data"][0]["attributes"]["value"] == "Provider B"
        assert result["data"][1]["attributes"]["value"] == "Provider A"

    def test_pagination(self):
        """Test pagination."""
        buckets = [{"key": f"Provider {i}", "doc_count": 100 - i} for i in range(20)]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            page=2,
            per_page=10,
        )

        assert len(result["data"]) == 10
        assert result["meta"]["currentPage"] == 2
        assert result["meta"]["totalPages"] == 2
        assert result["meta"]["totalCount"] == 20

    def test_q_facet_filtering(self):
        """Test filtering facet values with q_facet."""
        buckets = [
            {"key": "University of Minnesota", "doc_count": 50},
            {"key": "Minnesota State", "doc_count": 30},
            {"key": "Wisconsin University", "doc_count": 20},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            q_facet="University",
        )

        # Should filter to only values containing "University"
        assert result["meta"]["totalCount"] == 2
        assert all("University" in str(item["attributes"]["value"]) for item in result["data"])

    def test_q_facet_case_insensitive(self):
        """Test that q_facet filtering is case-insensitive."""
        buckets = [
            {"key": "University of Minnesota", "doc_count": 50},
            {"key": "university of wisconsin", "doc_count": 30},
            {"key": "Minnesota State", "doc_count": 20},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            q_facet="university",
        )

        # Should match both uppercase and lowercase
        assert result["meta"]["totalCount"] == 2

    def test_empty_buckets(self):
        """Test handling of empty buckets."""
        buckets = []
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
        )

        assert len(result["data"]) == 0
        assert result["meta"]["totalCount"] == 0
        assert result["meta"]["totalPages"] == 1

    def test_facet_value_structure(self):
        """Test that facet values have correct structure."""
        buckets = [{"key": "Provider A", "doc_count": 100}]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
        )

        facet_value = result["data"][0]
        assert facet_value["type"] == "facet_value"
        assert facet_value["id"] == "Provider A"
        assert "attributes" in facet_value
        assert "links" not in facet_value
        assert facet_value["attributes"]["value"] == "Provider A"
        assert facet_value["attributes"]["hits"] == 100
        assert facet_value["attributes"]["value"] == "Provider A"
        assert facet_value["attributes"]["hits"] == 100

    def test_default_sort(self):
        """Test that default sort is count_desc."""
        buckets = [
            {"key": "Provider B", "doc_count": 50},
            {"key": "Provider A", "doc_count": 100},
        ]
        search_criteria = {"query": None, "filters": {}}

        result = process_facet_response(
            buckets=buckets,
            facet_name="schema_provider_s",
            search_criteria=search_criteria,
            sort="invalid_sort",  # Invalid sort should default to count_desc
        )

        # Should default to count_desc
        assert result["data"][0]["attributes"]["hits"] == 100


class TestGetFacetValues:
    """Test get_facet_values function."""

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_basic_facet_retrieval(self, mock_es):
        """Test basic facet value retrieval."""
        # Mock Elasticsearch response
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {
                "facet_values": {
                    "buckets": [
                        {"key": "Provider A", "doc_count": 100},
                        {"key": "Provider B", "doc_count": 50},
                    ]
                }
            }
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        buckets = await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
        )

        assert len(buckets) == 2
        assert buckets[0]["key"] == "Provider A"
        assert buckets[0]["doc_count"] == 100

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_query_parameter(self, mock_es):
        """Test facet retrieval with query parameter."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 25}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query="water",
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
        )

        # Verify ES was called with query
        mock_es.search.assert_called_once()
        call_args = mock_es.search.call_args
        assert call_args.kwargs["query"] is not None

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_q_facet_parameter(self, mock_es):
        """Test facet retrieval with q_facet parameter."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {
                "facet_values": {"buckets": [{"key": "University of Minnesota", "doc_count": 50}]}
            }
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
            q_facet="University",
        )

        # Verify ES aggregation includes regex filter
        mock_es.search.assert_called_once()
        call_args = mock_es.search.call_args
        aggs = call_args.kwargs["aggs"]
        assert "facet_values" in aggs
        assert "include" in aggs["facet_values"]["terms"]

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_include_filters(self, mock_es):
        """Test facet retrieval with include_filters."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 15}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters={"dct_spatial_sm": ["Minnesota"]},
            exclude_filters=None,
            adv_q=None,
        )

        # Verify ES was called
        mock_es.search.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_exclude_filters(self, mock_es):
        """Test facet retrieval with exclude_filters."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 10}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters={"dct_spatial_sm": ["Wisconsin"]},
            adv_q=None,
        )

        # Verify ES was called
        mock_es.search.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_adv_q(self, mock_es):
        """Test facet retrieval with advanced query."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 5}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=[{"op": "AND", "f": "dct_title_s", "q": "Iowa"}],
        )

        # Verify ES was called
        mock_es.search.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_elasticsearch_error(self, mock_es):
        """Test handling of Elasticsearch errors."""
        mock_es.search = AsyncMock(side_effect=Exception("ES connection error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_facet_values(
                facet_name="schema_provider_s",
                query=None,
                fq=None,
                include_filters=None,
                exclude_filters=None,
                adv_q=None,
            )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es.search")
    async def test_invalid_facet_name(self, mock_es_search):
        """Test that invalid facet name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid facet name"):
            await get_facet_values(
                facet_name="invalid_facet",
                query=None,
                fq=None,
                include_filters=None,
                exclude_filters=None,
                adv_q=None,
            )

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_empty_aggregations(self, mock_es):
        """Test handling of empty aggregations."""
        mock_response = MagicMock()
        mock_response.body = {"aggregations": {}}
        mock_es.search = AsyncMock(return_value=mock_response)

        result = await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
        )

        assert result == []

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_size_parameter(self, mock_es):
        """Test that size parameter limits results."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {
                "facet_values": {
                    "buckets": [{"key": f"Provider {i}", "doc_count": 100 - i} for i in range(100)]
                }
            }
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
            size=50,
        )

        # Verify size was passed to ES aggregation
        mock_es.search.assert_called_once()
        call_args = mock_es.search.call_args
        aggs = call_args.kwargs["aggs"]
        assert aggs["facet_values"]["terms"]["size"] == 50

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_response_without_body_attribute(self, mock_es):
        """Test handling of response without .body attribute."""
        # Mock response as dict instead of object with .body
        mock_response = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 100}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        buckets = await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
        )

        assert len(buckets) == 1
        assert buckets[0]["key"] == "Provider A"

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_q_facet_regex_escaping(self, mock_es):
        """Test that q_facet properly escapes regex special characters."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {
                "facet_values": {"buckets": [{"key": "Provider (A)", "doc_count": 50}]}
            }
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
            q_facet="Provider (A)",  # Contains regex special characters
        )

        # Verify regex was escaped in aggregation
        mock_es.search.assert_called_once()
        call_args = mock_es.search.call_args
        aggs = call_args.kwargs["aggs"]
        assert "include" in aggs["facet_values"]["terms"]
        # Should escape parentheses
        assert "\\(" in aggs["facet_values"]["terms"]["include"]

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_adv_q_or_clause(self, mock_es):
        """Test facet retrieval with advanced query containing OR clause (should_clauses)."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 10}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters=None,
            adv_q=[{"op": "OR", "f": "dct_title_s", "q": "Iowa"}],
        )

        # Verify ES was called and should_clauses path was taken
        mock_es.search.assert_called_once()
        call_args = mock_es.search.call_args
        query = call_args.kwargs["query"]
        assert "should" in query["bool"]
        assert "minimum_should_match" in query["bool"]

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_fq_single_value(self, mock_es):
        """Test facet retrieval with fq containing single value (not list)."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 5}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq={"dct_spatial_sm": "Minnesota"},  # Single value, not list
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
        )

        # Verify ES was called
        mock_es.search.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_fq_field_resolution_to_keyword(self, mock_es):
        """Test that fq fields requiring .keyword resolution are correctly resolved."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Illinois", "doc_count": 10}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="dct_spatial_sm",
            query=None,
            fq={"gbl_resourceClass_sm": ["Maps"]},  # Field that requires .keyword resolution
            include_filters=None,
            exclude_filters=None,
            adv_q=None,
        )

        # Verify ES was called
        mock_es.search.assert_called_once()

        # Verify that the filter uses .keyword field
        call_args = mock_es.search.call_args
        query_dict = call_args.kwargs["query"]

        # Navigate through the bool query structure to find the filter
        filter_clauses = query_dict["bool"]["filter"]

        # Find the terms filter for gbl_resourceClass_sm
        terms_filter = None
        for clause in filter_clauses:
            if "terms" in clause:
                terms_filter = clause["terms"]
                break

        # Verify that gbl_resourceClass_sm.keyword is used, not gbl_resourceClass_sm
        assert terms_filter is not None, "Expected terms filter not found"
        assert "gbl_resourceClass_sm.keyword" in terms_filter, (
            f"Expected 'gbl_resourceClass_sm.keyword' in filter, "
            f"but got: {list(terms_filter.keys())}"
        )
        assert terms_filter["gbl_resourceClass_sm.keyword"] == ["Maps"]

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_include_filters_single_value(self, mock_es):
        """Test facet retrieval with include_filters containing single value."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 3}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters={"dct_spatial_sm": "Minnesota"},  # Single value, not list
            exclude_filters=None,
            adv_q=None,
        )

        # Verify ES was called
        mock_es.search.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.elasticsearch.search.es")
    async def test_with_exclude_filters_single_value(self, mock_es):
        """Test facet retrieval with exclude_filters containing single value."""
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {"facet_values": {"buckets": [{"key": "Provider A", "doc_count": 2}]}}
        }
        mock_es.search = AsyncMock(return_value=mock_response)

        await get_facet_values(
            facet_name="schema_provider_s",
            query=None,
            fq=None,
            include_filters=None,
            exclude_filters={"dct_spatial_sm": "Wisconsin"},  # Single value, not list
            adv_q=None,
        )

        # Verify ES was called
        mock_es.search.assert_called_once()
