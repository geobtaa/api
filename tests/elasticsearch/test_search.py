"""
Tests for the Elasticsearch search functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.elasticsearch.search import get_search_criteria, search_resources


class TestElasticsearchSearch:
    """Test cases for Elasticsearch search functionality."""

    def test_get_search_criteria(self):
        """Test the get_search_criteria function."""
        criteria = get_search_criteria(
            query="test query",
            fq={"dct_spatial_sm": ["Minnesota"]},
            skip=10,
            limit=20,
            sort=[{"_score": "desc"}],
        )

        assert criteria["query"] == "test query"
        assert criteria["filters"] == {"dct_spatial_sm": ["Minnesota"]}
        assert criteria["sort"] == [{"_score": "desc"}]

    @pytest.mark.asyncio
    async def test_search_resources_with_id_field_in_query_string(self):
        """Test that search_resources includes id field in query_string query."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources with a query
                await search_resources(
                    query="test-resource-id", fq=None, skip=0, limit=10, sort=None
                )

                # Verify that es.search was called
                mock_es.search.assert_called_once()

                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify the query structure
                assert search_query is not None
                assert "bool" in search_query
                assert "must" in search_query["bool"]

                # Find the query_string query in the must clause
                query_string_found = False
                for clause in search_query["bool"]["must"]:
                    if "query_string" in clause:
                        query_string_found = True
                        query_string = clause["query_string"]

                        # Verify that the id field is included with boost
                        fields = query_string["fields"]
                        id_field_found = False
                        for field in fields:
                            if field.startswith("id^"):
                                id_field_found = True
                                # Verify it has a high boost (^5)
                                assert field == "id^5"
                                break

                        assert id_field_found, (
                            "ID field with boost not found in query_string fields"
                        )
                        break

                assert query_string_found, "query_string query not found in search"

    @pytest.mark.asyncio
    async def test_search_resources_without_query(self):
        """Test search_resources without a query (match_all)."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources without a query
                await search_resources(query=None, fq=None, skip=0, limit=10, sort=None)

                # Verify that es.search was called
                mock_es.search.assert_called_once()

                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify the query structure for match_all
                assert search_query is not None
                assert "bool" in search_query
                assert "must" in search_query["bool"]
                assert {"match_all": {}} in search_query["bool"]["must"]

    @pytest.mark.asyncio
    async def test_search_resources_with_filters(self):
        """Test search_resources with filter queries."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources with filters
                await search_resources(
                    query="test",
                    fq={"dct_spatial_sm": ["Minnesota", "Wisconsin"]},
                    skip=0,
                    limit=10,
                    sort=None,
                )

                # Verify that es.search was called
                mock_es.search.assert_called_once()

                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify the query structure includes filters
                assert search_query is not None
                assert "bool" in search_query
                assert "filter" in search_query["bool"]

                # Verify the filter clause
                filter_clauses = search_query["bool"]["filter"]
                assert len(filter_clauses) == 1
                assert "terms" in filter_clauses[0]
                assert filter_clauses[0]["terms"]["dct_spatial_sm"] == ["Minnesota", "Wisconsin"]

    @pytest.mark.asyncio
    async def test_search_resources_error_handling(self):
        """Test search_resources error handling."""
        # Mock the Elasticsearch client to raise an exception
        mock_es = AsyncMock()
        mock_es.search.side_effect = Exception("Elasticsearch connection error")

        # Mock the es client
        with patch("app.elasticsearch.search.es", mock_es):
            # Call search_resources and expect an exception
            with pytest.raises(Exception) as exc_info:
                await search_resources(query="test", fq=None, skip=0, limit=10, sort=None)

            assert "Elasticsearch connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_resources_with_suggestions(self):
        """Test search_resources includes suggestions when query is provided."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
            "suggest": {
                "simple_phrase": [
                    {
                        "text": "test",
                        "offset": 0,
                        "length": 4,
                        "options": [{"text": "testing", "score": 0.8}],
                    }
                ]
            },
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources with a query
                await search_resources(query="test", fq=None, skip=0, limit=10, sort=None)

                # Verify that es.search was called with suggest parameter
                mock_es.search.assert_called_once()
                call_args = mock_es.search.call_args

                # Verify suggest was included in the call
                assert "suggest" in call_args.kwargs
                suggest = call_args.kwargs["suggest"]
                assert "text" in suggest
                assert "simple_phrase" in suggest

    @pytest.mark.asyncio
    async def test_search_resources_with_or_operator(self):
        """Test that OR operator is properly passed to query_string."""
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
                # Test OR query
                await search_resources(
                    query="Lake Superior OR Lake Erie", fq=None, skip=0, limit=10, sort=None
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the OR operator
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == "Lake Superior OR Lake Erie"

    @pytest.mark.asyncio
    async def test_search_resources_with_not_operator(self):
        """Test that NOT operator is properly passed to query_string."""
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
                # Test NOT query
                await search_resources(
                    query="Lake Superior NOT Michigan", fq=None, skip=0, limit=10, sort=None
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the NOT operator
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == "Lake Superior NOT Michigan"

    @pytest.mark.asyncio
    async def test_search_resources_with_grouping(self):
        """Test that parentheses grouping is properly passed to query_string."""
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
                # Test grouped query
                await search_resources(
                    query="(Lake Superior OR Lake Erie) AND Map",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None,
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the grouped query
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == "(Lake Superior OR Lake Erie) AND Map"

    @pytest.mark.asyncio
    async def test_search_resources_with_phrase_query(self):
        """Test that phrase queries with quotes are properly passed to query_string."""
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
                # Test phrase query
                await search_resources(
                    query='"Lake Superior"', fq=None, skip=0, limit=10, sort=None
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the phrase query with quotes
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == '"Lake Superior"'

    @pytest.mark.asyncio
    async def test_query_string_has_correct_parameters(self):
        """Test that query_string has the correct configuration parameters."""
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
                await search_resources(query="test query", fq=None, skip=0, limit=10, sort=None)

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                query_string_clause = search_query["bool"]["must"][0]["query_string"]

                # Verify configuration
                assert query_string_clause["default_operator"] == "AND"
                assert query_string_clause["analyze_wildcard"] is True
                assert query_string_clause["allow_leading_wildcard"] is True
