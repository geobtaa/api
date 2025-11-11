"""
Tests for advanced multi-field search functionality.

This file contains:
- Validation tests (test API validation without hitting Elasticsearch)
- Query structure tests (verify queries are built correctly using mocks)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestAdvancedSearchValidation:
    """Test validation of advanced query parameters."""

    async def test_advanced_queries_missing_operator(self, async_client: AsyncClient):
        """Test that missing operator returns 400 error."""
        payload = {"advanced_queries": [{"field": "dct_title_s", "query": "Iowa"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        assert "operator" in response.json()["detail"].lower()

    async def test_advanced_queries_missing_field(self, async_client: AsyncClient):
        """Test that missing field returns 400 error."""
        payload = {"advanced_queries": [{"operator": "AND", "query": "Iowa"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        assert "field" in response.json()["detail"].lower()

    async def test_advanced_queries_missing_query(self, async_client: AsyncClient):
        """Test that missing query returns 400 error."""
        payload = {"advanced_queries": [{"operator": "AND", "field": "dct_title_s"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        assert "query" in response.json()["detail"].lower()

    async def test_advanced_queries_empty_query(self, async_client: AsyncClient):
        """Test that empty query returns 400 error."""
        payload = {"advanced_queries": [{"operator": "AND", "field": "dct_title_s", "query": ""}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400

    async def test_advanced_queries_empty_field(self, async_client: AsyncClient):
        """Test that empty field returns 400 error."""
        payload = {"advanced_queries": [{"operator": "AND", "field": "", "query": "Iowa"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400

    async def test_advanced_queries_invalid_operator(self, async_client: AsyncClient):
        """Test that invalid operator returns 400 error."""
        payload = {
            "advanced_queries": [{"operator": "XOR", "field": "dct_title_s", "query": "Iowa"}]
        }
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        assert "invalid operator" in response.json()["detail"].lower()

    async def test_advanced_queries_empty_list(self, async_client: AsyncClient):
        """Test that empty list returns 400 error."""
        payload = {"advanced_queries": []}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400

    async def test_advanced_queries_not_list(self, async_client: AsyncClient):
        """Test that non-list advanced_queries returns 400 error."""
        payload = {"advanced_queries": {"operator": "AND", "field": "dct_title_s", "query": "Iowa"}}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400


class TestAdvancedSearchFieldNames:
    """Test that any Elasticsearch field name can be used."""

    @pytest.mark.parametrize(
        "field_name",
        [
            "dct_title_s",
            "dct_description_sm",
            "dct_creator_sm",
            "dct_publisher_sm",
            "schema_provider_s",
            "gbl_resourceClass_sm",
            "gbl_resourceType_sm",
            "dct_subject_sm",
            "dcat_keyword_sm",
        ],
    )
    async def test_es_field_names_accepted(self, async_client: AsyncClient, field_name):
        """Test that Elasticsearch field names are accepted."""
        payload = {"advanced_queries": [{"operator": "AND", "field": field_name, "query": "test"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        # Should not return validation error for field name format
        # (Elasticsearch will validate if field exists)
        assert (
            response.status_code != 400 or "field" not in response.json().get("detail", "").lower()
        )


class TestAdvancedSearchQueryStructure:
    """Test that advanced queries are built into correct Elasticsearch query structure."""

    @pytest.mark.asyncio
    async def test_and_operator_query_structure(self):
        """Test that AND operator creates correct must clause."""
        from app.elasticsearch.search import _build_advanced_query

        advanced_queries = [{"operator": "AND", "field": "dct_title_s", "query": "Iowa"}]
        result = _build_advanced_query(advanced_queries)

        assert len(result["must"]) == 1
        assert len(result["should"]) == 0
        assert len(result["must_not"]) == 0
        assert result["must"][0]["match"]["dct_title_s"]["query"] == "Iowa"
        assert result["must"][0]["match"]["dct_title_s"]["operator"] == "and"

    @pytest.mark.asyncio
    async def test_or_operator_query_structure(self):
        """Test that OR operator creates correct should clause."""
        from app.elasticsearch.search import _build_advanced_query

        advanced_queries = [{"operator": "OR", "field": "dct_title_s", "query": "Iowa"}]
        result = _build_advanced_query(advanced_queries)

        assert len(result["must"]) == 0
        assert len(result["should"]) == 1
        assert len(result["must_not"]) == 0
        assert result["should"][0]["match"]["dct_title_s"]["query"] == "Iowa"

    @pytest.mark.asyncio
    async def test_not_operator_query_structure(self):
        """Test that NOT operator creates correct must_not clause."""
        from app.elasticsearch.search import _build_advanced_query

        advanced_queries = [{"operator": "NOT", "field": "dct_title_s", "query": "Wisconsin"}]
        result = _build_advanced_query(advanced_queries)

        assert len(result["must"]) == 0
        assert len(result["should"]) == 0
        assert len(result["must_not"]) == 1
        assert result["must_not"][0]["match"]["dct_title_s"]["query"] == "Wisconsin"

    @pytest.mark.asyncio
    async def test_case_insensitive_operators(self):
        """Test that operators are normalized to uppercase by validation."""
        from app.api.v1.advanced_search_utils import validate_advanced_queries
        from app.elasticsearch.search import _build_advanced_query

        # Validation normalizes operators to uppercase
        advanced_queries = [
            {"operator": "and", "field": "dct_title_s", "query": "Iowa"},
            {"operator": "or", "field": "dct_description_sm", "query": "Water"},
            {"operator": "not", "field": "dct_subject_sm", "query": "River"},
        ]
        validated_queries = validate_advanced_queries(advanced_queries)
        result = _build_advanced_query(validated_queries)

        # All should be properly routed after validation normalizes to uppercase
        assert len(result["must"]) == 1  # AND -> must
        assert len(result["should"]) == 1  # OR -> should
        assert len(result["must_not"]) == 1  # NOT -> must_not

        # Verify operators were normalized
        assert validated_queries[0]["operator"] == "AND"
        assert validated_queries[1]["operator"] == "OR"
        assert validated_queries[2]["operator"] == "NOT"

    @pytest.mark.asyncio
    async def test_multiple_and_clauses_structure(self):
        """Test that multiple AND clauses are all added to must."""
        from app.elasticsearch.search import _build_advanced_query

        advanced_queries = [
            {"operator": "AND", "field": "dct_title_s", "query": "Iowa"},
            {"operator": "AND", "field": "dct_description_sm", "query": "Water"},
        ]
        result = _build_advanced_query(advanced_queries)

        assert len(result["must"]) == 2
        assert result["must"][0]["match"]["dct_title_s"]["query"] == "Iowa"
        assert result["must"][1]["match"]["dct_description_sm"]["query"] == "Water"

    @pytest.mark.asyncio
    async def test_mixed_operators_structure(self):
        """Test that mixed operators are routed to correct clauses."""
        from app.elasticsearch.search import _build_advanced_query

        advanced_queries = [
            {"operator": "AND", "field": "dct_title_s", "query": "Iowa"},
            {"operator": "NOT", "field": "dct_title_s", "query": "Wisconsin"},
            {"operator": "AND", "field": "dct_description_sm", "query": "Water"},
            {"operator": "NOT", "field": "dct_subject_sm", "query": "River"},
        ]
        result = _build_advanced_query(advanced_queries)

        assert len(result["must"]) == 2
        assert len(result["should"]) == 0
        assert len(result["must_not"]) == 2

    @pytest.mark.asyncio
    async def test_advanced_queries_integrated_into_search(self):
        """Test that advanced queries are correctly integrated into the full search query."""
        from app.elasticsearch.search import search_resources

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    advanced_queries=[
                        {"operator": "AND", "field": "dct_title_s", "query": "Iowa"},
                        {"operator": "NOT", "field": "dct_title_s", "query": "Wisconsin"},
                    ],
                )

                # Verify Elasticsearch was called
                assert mock_es.search.called

                # Get the query that was sent
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify the bool query structure
                assert "bool" in search_query
                bool_query = search_query["bool"]

                # Verify must clauses (from AND operator)
                assert "must" in bool_query
                assert len(bool_query["must"]) == 1
                assert bool_query["must"][0]["match"]["dct_title_s"]["query"] == "Iowa"

                # Verify must_not clauses (from NOT operator)
                assert "must_not" in bool_query
                assert len(bool_query["must_not"]) == 1
                assert bool_query["must_not"][0]["match"]["dct_title_s"]["query"] == "Wisconsin"

    @pytest.mark.asyncio
    async def test_q_and_advanced_queries_combined(self):
        """Test that q parameter and advanced_queries are combined correctly."""
        from app.elasticsearch.search import search_resources

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query="Wisconsin",
                    advanced_queries=[{"operator": "AND", "field": "dct_title_s", "query": "Iowa"}],
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                bool_query = search_query["bool"]

                # Should have both q (as query_string) and advanced_queries (as match) in must
                assert "must" in bool_query
                must_clauses = bool_query["must"]
                assert len(must_clauses) == 2

                # First clause should be query_string from q parameter
                assert "query_string" in must_clauses[0]
                assert must_clauses[0]["query_string"]["query"] == "Wisconsin"

                # Second clause should be match from advanced_queries
                assert "match" in must_clauses[1]
                assert must_clauses[1]["match"]["dct_title_s"]["query"] == "Iowa"


class TestAdvancedSearchFields:
    """Test that various Elasticsearch fields are accepted in query structure."""

    @pytest.mark.parametrize(
        "field_name",
        [
            "dct_title_s",
            "dct_description_sm",
            "dct_creator_sm",
            "dct_publisher_sm",
            "schema_provider_s",
            "gbl_resourceClass_sm",
            "gbl_resourceType_sm",
            "dct_subject_sm",
            "dcat_keyword_sm",
        ],
    )
    @pytest.mark.asyncio
    async def test_various_es_fields_in_query_structure(self, field_name):
        """Test that various Elasticsearch fields are correctly used in query structure."""
        from app.elasticsearch.search import _build_advanced_query

        advanced_queries = [{"operator": "AND", "field": field_name, "query": "test"}]
        result = _build_advanced_query(advanced_queries)

        assert len(result["must"]) == 1
        assert field_name in result["must"][0]["match"]
        assert result["must"][0]["match"][field_name]["query"] == "test"


class TestAdvancedSearchGETEndpoint:
    """Test GET endpoint with advanced_queries."""

    async def test_get_with_invalid_json(self, async_client: AsyncClient):
        """Test GET endpoint with invalid JSON returns 400."""
        response = await async_client.get("/api/v1/search?advanced_queries=invalid{json")
        assert response.status_code == 400


class TestAdvancedSearchWithOtherParams:
    """Test that advanced queries are correctly combined with other search parameters."""

    @pytest.mark.asyncio
    async def test_advanced_queries_with_pagination_structure(self):
        """Test that pagination parameters are passed through correctly."""
        from app.elasticsearch.search import search_resources

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    advanced_queries=[{"operator": "AND", "field": "dct_title_s", "query": "Iowa"}],
                    skip=10,
                    limit=5,
                )

                call_args = mock_es.search.call_args
                assert call_args.kwargs.get("from_") == 10
                assert call_args.kwargs.get("size") == 5

    @pytest.mark.asyncio
    async def test_advanced_queries_with_filters_structure(self):
        """Test that filters are correctly combined with advanced queries."""
        from app.elasticsearch.search import search_resources

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    advanced_queries=[{"operator": "AND", "field": "dct_title_s", "query": "Iowa"}],
                    include_filters={"dct_spatial_sm": ["Minnesota"]},
                    exclude_filters={"gbl_resourceType_sm": ["Dataset"]},
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                bool_query = search_query["bool"]

                # Should have filter clauses
                assert "filter" in bool_query
                # Should still have advanced query in must
                assert "must" in bool_query
                assert len(bool_query["must"]) == 1


class TestAdvancedSearchBackwardCompatibility:
    """Test that existing q and search_field parameters still work with advanced queries."""

    @pytest.mark.asyncio
    async def test_q_with_multiple_advanced_queries_structure(self):
        """Test that q works with multiple advanced query clauses in query structure."""
        from app.elasticsearch.search import search_resources

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query="water",
                    advanced_queries=[
                        {"operator": "AND", "field": "dct_title_s", "query": "Iowa"},
                        {"operator": "NOT", "field": "dct_title_s", "query": "Wisconsin"},
                        {"operator": "AND", "field": "dct_description_sm", "query": "river"},
                    ],
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                bool_query = search_query["bool"]

                # Should have q as query_string in must
                assert "must" in bool_query
                must_clauses = bool_query["must"]
                assert len(must_clauses) >= 1
                assert "query_string" in must_clauses[0]

                # Should have advanced query AND clauses in must
                match_clauses = [c for c in must_clauses if "match" in c]
                assert len(match_clauses) == 2  # Two AND clauses

                # Should have NOT clauses in must_not
                assert "must_not" in bool_query
                assert len(bool_query["must_not"]) == 1
