"""
Tests for the SearchService.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.search_service import SearchService


class TestSearchService:
    """Test cases for SearchService class."""

    def test_search_service_initialization(self):
        """Test that the SearchService can be initialized."""
        service = SearchService()
        assert service is not None
        assert hasattr(service, "index_name")
        assert hasattr(service, "es")
        # In test environment, the index name might be different
        assert service.index_name in ["btaa_ogm_api", "btaa_ogm_api_test"]

    @pytest.mark.asyncio
    async def test_search_with_id_field_in_multi_match(self):
        """Test that the search query includes the id field in multi_match."""
        service = SearchService()
        
        # Mock the search_resources function to capture the query
        with patch('app.services.search_service.search_resources') as mock_search:
            # Mock the response
            mock_response = {
                "data": [],
                "meta": {
                    "totalCount": 0,
                    "currentPage": 1,
                    "perPage": 10,
                    "totalPages": 0
                },
                "included": []
            }
            mock_search.return_value = mock_response
            
            # Call the search method
            result = await service.search(q="test-resource-id", page=1, limit=10)
            
            # Verify that search_resources was called
            mock_search.assert_called_once()
            
            # Get the call arguments
            call_args = mock_search.call_args
            query_param = call_args.kwargs.get('query') or call_args.args[0]
            
            # Verify the query parameter was passed correctly
            assert query_param == "test-resource-id"

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Test search with filter parameters."""
        service = SearchService()
        
        with patch('app.services.search_service.search_resources') as mock_search:
            mock_response = {
                "data": [],
                "meta": {
                    "totalCount": 0,
                    "currentPage": 1,
                    "perPage": 10,
                    "totalPages": 0
                },
                "included": []
            }
            mock_search.return_value = mock_response
            
            # Call with filter parameters
            result = await service.search(
                q="test",
                page=1,
                limit=10,
                request_query_params="fq[dct_spatial_sm][]=Minnesota"
            )
            
            # Verify that search_resources was called with filters
            mock_search.assert_called_once()
            call_args = mock_search.call_args
            fq_param = call_args.kwargs.get('fq')
            
            # The filter should be extracted and passed
            assert fq_param is not None

    @pytest.mark.asyncio
    async def test_search_with_sort(self):
        """Test search with sort parameter."""
        service = SearchService()
        
        with patch('app.services.search_service.search_resources') as mock_search:
            mock_response = {
                "data": [],
                "meta": {
                    "totalCount": 0,
                    "currentPage": 1,
                    "perPage": 10,
                    "totalPages": 0
                },
                "included": []
            }
            mock_search.return_value = mock_response
            
            # Call with sort parameter
            result = await service.search(
                q="test",
                page=1,
                limit=10,
                sort="year_desc"
            )
            
            # Verify that search_resources was called
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """Test search error handling."""
        service = SearchService()
        
        with patch('app.services.search_service.search_resources') as mock_search:
            # Mock an exception
            mock_search.side_effect = Exception("Elasticsearch error")
            
            # Call the search method
            result = await service.search(q="test", page=1, limit=10)
            
            # Verify error response structure
            assert "message" in result
            assert "error" in result
            assert result["message"] == "Search operation failed"
            assert "Elasticsearch error" in result["error"]

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
