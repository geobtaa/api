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


def error_detail(response):
    payload = response.json()
    if "errors" in payload:
        return payload["errors"][0]["detail"]
    return payload["detail"]


class TestAdvancedSearchValidation:
    """Test validation of advanced query parameters."""

    async def test_adv_q_missing_operator(self, async_client: AsyncClient):
        """Test that missing operator returns 400 error."""
        payload = {"adv_q": [{"f": "dct_title_s", "q": "Iowa"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        assert "op" in error_detail(response).lower()

    async def test_adv_q_missing_field(self, async_client: AsyncClient):
        """Test that missing field returns 400 error."""
        payload = {"adv_q": [{"op": "AND", "q": "Iowa"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        detail = error_detail(response).lower()
        assert "f" in detail or "field" in detail

    async def test_adv_q_missing_query(self, async_client: AsyncClient):
        """Test that missing query returns 400 error."""
        payload = {"adv_q": [{"op": "AND", "f": "dct_title_s"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        detail = error_detail(response).lower()
        assert "q" in detail or "query" in detail

    async def test_adv_q_empty_query(self, async_client: AsyncClient):
        """Test that empty query returns 400 error."""
        payload = {"adv_q": [{"op": "AND", "f": "dct_title_s", "q": ""}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400

    async def test_adv_q_empty_field(self, async_client: AsyncClient):
        """Test that empty field returns 400 error."""
        payload = {"adv_q": [{"op": "AND", "f": "", "q": "Iowa"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400

    async def test_adv_q_invalid_operator(self, async_client: AsyncClient):
        """Test that invalid operator returns 400 error."""
        payload = {"adv_q": [{"op": "XOR", "f": "dct_title_s", "q": "Iowa"}]}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400
        assert "invalid operator" in error_detail(response).lower()

    async def test_adv_q_empty_list(self, async_client: AsyncClient):
        """Test that empty list returns 400 error."""
        payload = {"adv_q": []}
        response = await async_client.post("/api/v1/search", json=payload)
        assert response.status_code == 400

    async def test_adv_q_not_list(self, async_client: AsyncClient):
        """Test that non-list adv_q returns 400 error."""
        payload = {"adv_q": {"op": "AND", "f": "dct_title_s", "q": "Iowa"}}
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
        payload = {"adv_q": [{"op": "AND", "f": field_name, "q": "test"}]}
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

        adv_q = [{"op": "AND", "f": "dct_title_s", "q": "Iowa"}]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 1
        assert len(result["should"]) == 0
        assert len(result["must_not"]) == 0
        assert result["must"][0]["match"]["dct_title_s"]["query"] == "Iowa"
        assert result["must"][0]["match"]["dct_title_s"]["operator"] == "and"

    @pytest.mark.asyncio
    async def test_or_operator_query_structure(self):
        """Test that OR operator creates correct should clause."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [{"op": "OR", "f": "dct_title_s", "q": "Iowa"}]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 0
        assert len(result["should"]) == 1
        assert len(result["must_not"]) == 0
        assert result["should"][0]["match"]["dct_title_s"]["query"] == "Iowa"

    @pytest.mark.asyncio
    async def test_not_operator_query_structure(self):
        """Test that NOT operator creates correct must_not clause."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [{"op": "NOT", "f": "dct_title_s", "q": "Wisconsin"}]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 0
        assert len(result["should"]) == 0
        assert len(result["must_not"]) == 1
        assert result["must_not"][0]["match"]["dct_title_s"]["query"] == "Wisconsin"

    @pytest.mark.asyncio
    async def test_case_insensitive_operators(self):
        """Test that operators are normalized to uppercase by validation."""
        from app.api.v1.advanced_search_utils import validate_adv_q
        from app.elasticsearch.search import _build_advanced_query

        # Validation normalizes operators to uppercase
        adv_q = [
            {"op": "and", "f": "dct_title_s", "q": "Iowa"},
            {"op": "or", "f": "dct_description_sm", "q": "Water"},
            {"op": "not", "f": "dct_subject_sm", "q": "River"},
        ]
        validated_queries = validate_adv_q(adv_q)
        result = _build_advanced_query(validated_queries)

        # All should be properly routed after validation normalizes to uppercase
        assert len(result["must"]) == 1  # AND -> must
        assert len(result["should"]) == 1  # OR -> should
        assert len(result["must_not"]) == 1  # NOT -> must_not

        # Verify operators were normalized
        assert validated_queries[0]["op"] == "AND"
        assert validated_queries[0]["f"] == "dct_title_s"
        assert validated_queries[0]["q"] == "Iowa"
        assert validated_queries[1]["op"] == "OR"
        assert validated_queries[1]["f"] == "dct_description_sm"
        assert validated_queries[1]["q"] == "Water"
        assert validated_queries[2]["op"] == "NOT"
        assert validated_queries[2]["f"] == "dct_subject_sm"
        assert validated_queries[2]["q"] == "River"

    @pytest.mark.asyncio
    async def test_multiple_and_clauses_structure(self):
        """Test that multiple AND clauses are all added to must."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [
            {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
            {"op": "AND", "f": "dct_description_sm", "q": "Water"},
        ]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 2
        assert result["must"][0]["match"]["dct_title_s"]["query"] == "Iowa"
        assert result["must"][1]["match"]["dct_description_sm"]["query"] == "Water"

    @pytest.mark.asyncio
    async def test_mixed_operators_structure(self):
        """Test that mixed operators are routed to correct clauses."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [
            {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
            {"op": "NOT", "f": "dct_title_s", "q": "Wisconsin"},
            {"op": "AND", "f": "dct_description_sm", "q": "Water"},
            {"op": "NOT", "f": "dct_subject_sm", "q": "River"},
        ]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 2
        assert len(result["should"]) == 0
        assert len(result["must_not"]) == 2

    @pytest.mark.asyncio
    async def test_adv_q_integrated_into_search(self):
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
                    adv_q=[
                        {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
                        {"op": "NOT", "f": "dct_title_s", "q": "Wisconsin"},
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
    async def test_q_and_adv_q_combined(self):
        """Test that q parameter and adv_q are combined correctly."""
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
                    adv_q=[{"op": "AND", "f": "dct_title_s", "q": "Iowa"}],
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                bool_query = search_query["bool"]

                # Should have both q (as query_string) and adv_q (as match) in must
                assert "must" in bool_query
                must_clauses = bool_query["must"]
                assert len(must_clauses) == 2

                # First clause should be query_string from q parameter
                assert "query_string" in must_clauses[0]
                assert must_clauses[0]["query_string"]["query"] == "Wisconsin"

                # Second clause should be match from adv_q
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

        adv_q = [{"op": "AND", "f": field_name, "q": "test"}]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 1
        assert field_name in result["must"][0]["match"]
        assert result["must"][0]["match"][field_name]["query"] == "test"


class TestAdvancedSearchGETEndpoint:
    """Test GET endpoint with adv_q."""

    async def test_get_with_invalid_json(self, async_client: AsyncClient):
        """Test GET endpoint with invalid JSON returns 400."""
        response = await async_client.get("/api/v1/search?adv_q=invalid{json")
        assert response.status_code == 400


class TestAdvancedSearchWithOtherParams:
    """Test that advanced queries are correctly combined with other search parameters."""

    @pytest.mark.asyncio
    async def test_adv_q_with_pagination_structure(self):
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
                    adv_q=[{"op": "AND", "f": "dct_title_s", "q": "Iowa"}],
                    skip=10,
                    limit=5,
                )

                call_args = mock_es.search.call_args
                assert call_args.kwargs.get("from_") == 10
                assert call_args.kwargs.get("size") == 5

    @pytest.mark.asyncio
    async def test_adv_q_with_filters_structure(self):
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
                    adv_q=[{"op": "AND", "f": "dct_title_s", "q": "Iowa"}],
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
    async def test_q_with_multiple_adv_q_structure(self):
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
                    adv_q=[
                        {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
                        {"op": "NOT", "f": "dct_title_s", "q": "Wisconsin"},
                        {"op": "AND", "f": "dct_description_sm", "q": "river"},
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


class TestAdvancedSearchAllFields:
    """Test that 'all_fields' field name uses query_string across multiple fields."""

    @pytest.mark.asyncio
    async def test_all_fields_uses_query_string(self):
        """Test that all_fields uses query_string across multiple fields."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [{"op": "AND", "f": "all_fields", "q": "water"}]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 1
        assert "query_string" in result["must"][0]
        query_string = result["must"][0]["query_string"]
        assert query_string["query"] == "water"
        assert "fields" in query_string
        # Should search across multiple fields with boosts
        assert len(query_string["fields"]) > 1
        assert "dct_title_s^3" in query_string["fields"]
        assert "dct_description_sm^2" in query_string["fields"]

    @pytest.mark.asyncio
    async def test_all_fields_case_insensitive(self):
        """Test that all_fields works with different case variations."""
        from app.elasticsearch.search import _build_advanced_query

        for field_variant in ["all_fields", "ALL_FIELDS", "All_Fields", "all", "*"]:
            adv_q = [{"op": "AND", "f": field_variant, "q": "test"}]
            result = _build_advanced_query(adv_q)

            assert len(result["must"]) == 1
            assert "query_string" in result["must"][0]

    @pytest.mark.asyncio
    async def test_all_fields_with_phrase(self):
        """Test that all_fields handles phrase queries correctly."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [{"op": "AND", "f": "all_fields", "q": '"exact phrase"'}]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 1
        assert "query_string" in result["must"][0]
        # query_string should preserve quotes for phrase matching
        assert result["must"][0]["query_string"]["query"] == '"exact phrase"'


class TestAdvancedSearchOROperator:
    """Test OR operator behavior, especially when mixed with AND on same field."""

    @pytest.mark.asyncio
    async def test_or_operator_single_clause(self):
        """Test that single OR clause goes to should."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [{"op": "OR", "f": "dct_title_s", "q": "Iowa"}]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 0
        assert len(result["should"]) == 1
        assert len(result["must_not"]) == 0
        assert result["should"][0]["match"]["dct_title_s"]["query"] == "Iowa"

    @pytest.mark.asyncio
    async def test_and_then_or_same_field_treated_as_or(self):
        """Test that AND+OR on same field are all treated as OR clauses."""
        from app.elasticsearch.search import _build_advanced_query

        # This is the bug case: AND then OR on same field should be OR
        adv_q = [
            {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
            {"op": "OR", "f": "dct_title_s", "q": "Wisconsin"},
        ]
        result = _build_advanced_query(adv_q)

        # Both should be in should_clauses, not must
        assert len(result["must"]) == 0
        assert len(result["should"]) == 2
        assert len(result["must_not"]) == 0

        # Both should be match queries on dct_title_s
        assert result["should"][0]["match"]["dct_title_s"]["query"] == "Iowa"
        assert result["should"][1]["match"]["dct_title_s"]["query"] == "Wisconsin"

    @pytest.mark.asyncio
    async def test_multiple_or_same_field(self):
        """Test that multiple OR clauses on same field all go to should."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [
            {"op": "OR", "f": "dct_title_s", "q": "Iowa"},
            {"op": "OR", "f": "dct_title_s", "q": "Wisconsin"},
            {"op": "OR", "f": "dct_title_s", "q": "Minnesota"},
        ]
        result = _build_advanced_query(adv_q)

        assert len(result["must"]) == 0
        assert len(result["should"]) == 3
        assert len(result["must_not"]) == 0

    @pytest.mark.asyncio
    async def test_or_different_fields_not_treated_as_or(self):
        """Test that OR clauses on different fields work normally (not all as OR)."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [
            {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
            {"op": "OR", "f": "dct_description_sm", "q": "Water"},
        ]
        result = _build_advanced_query(adv_q)

        # Should work normally: AND in must, OR in should
        assert len(result["must"]) == 1
        assert len(result["should"]) == 1
        assert result["must"][0]["match"]["dct_title_s"]["query"] == "Iowa"
        assert result["should"][0]["match"]["dct_description_sm"]["query"] == "Water"

    @pytest.mark.asyncio
    async def test_or_with_not_clause_same_field(self):
        """Test that NOT clauses are excluded from OR grouping."""
        from app.elasticsearch.search import _build_advanced_query

        adv_q = [
            {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
            {"op": "OR", "f": "dct_title_s", "q": "Wisconsin"},
            {"op": "NOT", "f": "dct_title_s", "q": "Minnesota"},
        ]
        result = _build_advanced_query(adv_q)

        # Iowa and Wisconsin should both be in should (treated as OR)
        assert len(result["must"]) == 0
        assert len(result["should"]) == 2
        assert len(result["must_not"]) == 1

        # NOT clause should be separate
        assert result["must_not"][0]["match"]["dct_title_s"]["query"] == "Minnesota"

    @pytest.mark.asyncio
    async def test_or_same_field_integration(self):
        """Test that OR on same field works correctly in full search."""
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
                    adv_q=[
                        {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
                        {"op": "OR", "f": "dct_title_s", "q": "Wisconsin"},
                    ],
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                bool_query = search_query["bool"]

                # Should have both in should_clauses (treated as OR)
                assert "should" in bool_query
                assert len(bool_query["should"]) == 2
                assert bool_query["minimum_should_match"] == 1

                # Should NOT have must clauses
                assert "must" not in bool_query or len(bool_query.get("must", [])) == 0
