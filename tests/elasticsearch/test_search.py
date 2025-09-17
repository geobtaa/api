"""
Tests for the Elasticsearch search functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.elasticsearch.search import search_resources, get_search_criteria


class TestElasticsearchSearch:
    """Test cases for Elasticsearch search functionality."""

    def test_get_search_criteria(self):
        """Test the get_search_criteria function."""
        criteria = get_search_criteria(
            query="test query",
            fq={"dct_spatial_sm": ["Minnesota"]},
            skip=10,
            limit=20,
            sort=[{"_score": "desc"}]
        )
        
        assert criteria["query"] == "test query"
        assert criteria["filters"] == {"dct_spatial_sm": ["Minnesota"]}
        assert criteria["sort"] == [{"_score": "desc"}]

    @pytest.mark.asyncio
    async def test_search_resources_with_id_field_in_multi_match(self):
        """Test that search_resources includes id field in multi_match query."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {
                "total": {"value": 0},
                "hits": []
            },
            "took": 1,
            "aggregations": {}
        }
        mock_es.search.return_value = mock_response
        
        # Mock the database fetch_all
        with patch('app.elasticsearch.search.database.fetch_all') as mock_fetch:
            mock_fetch.return_value = []
            
            # Mock the es client
            with patch('app.elasticsearch.search.es', mock_es):
                # Call search_resources with a query
                result = await search_resources(
                    query="test-resource-id",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None
                )
                
                # Verify that es.search was called
                mock_es.search.assert_called_once()
                
                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get('query')
                
                # Verify the query structure
                assert search_query is not None
                assert "bool" in search_query
                assert "must" in search_query["bool"]
                
                # Find the multi_match query in the must clause
                multi_match_found = False
                for clause in search_query["bool"]["must"]:
                    if "multi_match" in clause:
                        multi_match_found = True
                        multi_match = clause["multi_match"]
                        
                        # Verify that the id field is included with boost
                        fields = multi_match["fields"]
                        id_field_found = False
                        for field in fields:
                            if field.startswith("id^"):
                                id_field_found = True
                                # Verify it has a high boost (^5)
                                assert field == "id^5"
                                break
                        
                        assert id_field_found, "ID field with boost not found in multi_match fields"
                        break
                
                assert multi_match_found, "multi_match query not found in search"

    @pytest.mark.asyncio
    async def test_search_resources_without_query(self):
        """Test search_resources without a query (match_all)."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {
                "total": {"value": 0},
                "hits": []
            },
            "took": 1,
            "aggregations": {}
        }
        mock_es.search.return_value = mock_response
        
        # Mock the database fetch_all
        with patch('app.elasticsearch.search.database.fetch_all') as mock_fetch:
            mock_fetch.return_value = []
            
            # Mock the es client
            with patch('app.elasticsearch.search.es', mock_es):
                # Call search_resources without a query
                result = await search_resources(
                    query=None,
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None
                )
                
                # Verify that es.search was called
                mock_es.search.assert_called_once()
                
                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get('query')
                
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
            "hits": {
                "total": {"value": 0},
                "hits": []
            },
            "took": 1,
            "aggregations": {}
        }
        mock_es.search.return_value = mock_response
        
        # Mock the database fetch_all
        with patch('app.elasticsearch.search.database.fetch_all') as mock_fetch:
            mock_fetch.return_value = []
            
            # Mock the es client
            with patch('app.elasticsearch.search.es', mock_es):
                # Call search_resources with filters
                result = await search_resources(
                    query="test",
                    fq={"dct_spatial_sm": ["Minnesota", "Wisconsin"]},
                    skip=0,
                    limit=10,
                    sort=None
                )
                
                # Verify that es.search was called
                mock_es.search.assert_called_once()
                
                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get('query')
                
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
        with patch('app.elasticsearch.search.es', mock_es):
            # Call search_resources and expect an exception
            with pytest.raises(Exception) as exc_info:
                await search_resources(
                    query="test",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None
                )
            
            assert "Elasticsearch connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_resources_with_suggestions(self):
        """Test search_resources includes suggestions when query is provided."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {
                "total": {"value": 0},
                "hits": []
            },
            "took": 1,
            "aggregations": {},
            "suggest": {
                "simple_phrase": [
                    {
                        "text": "test",
                        "offset": 0,
                        "length": 4,
                        "options": [
                            {
                                "text": "testing",
                                "score": 0.8
                            }
                        ]
                    }
                ]
            }
        }
        mock_es.search.return_value = mock_response
        
        # Mock the database fetch_all
        with patch('app.elasticsearch.search.database.fetch_all') as mock_fetch:
            mock_fetch.return_value = []
            
            # Mock the es client
            with patch('app.elasticsearch.search.es', mock_es):
                # Call search_resources with a query
                result = await search_resources(
                    query="test",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None
                )
                
                # Verify that es.search was called with suggest parameter
                mock_es.search.assert_called_once()
                call_args = mock_es.search.call_args
                
                # Verify suggest was included in the call
                assert "suggest" in call_args.kwargs
                suggest = call_args.kwargs["suggest"]
                assert "text" in suggest
                assert "simple_phrase" in suggest
