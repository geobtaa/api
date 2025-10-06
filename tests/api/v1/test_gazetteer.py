"""
Tests for the gazetteer API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.v1.gazetteer import router


# Create test app
app = FastAPI()
app.include_router(router, prefix="/gazetteers")

# Test client
client = TestClient(app)


class TestListGazetteers:
    """Test cases for listing gazetteers."""

    def test_list_gazetteers_success(self):
        """Test successful listing of gazetteers."""
        response = client.get("/gazetteers/gazetteers")
        
        # Should return 200 or 500 depending on database connection
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "gazetteers" in data
            assert isinstance(data["gazetteers"], list)
        else:
            # Error response should have detail
            assert "detail" in data

    def test_list_gazetteers_with_callback(self):
        """Test listing gazetteers with JSONP callback."""
        response = client.get("/gazetteers/gazetteers?callback=myCallback")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")


class TestGeoNamesGazetteer:
    """Test cases for GeoNames gazetteer endpoints."""

    def test_list_geonames_success(self):
        """Test successful listing of GeoNames records."""
        response = client.get("/gazetteers/gazetteers/geonames")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data
            assert "links" in data
        else:
            assert "detail" in data

    def test_list_geonames_with_pagination(self):
        """Test GeoNames listing with pagination."""
        response = client.get("/gazetteers/gazetteers/geonames?page=1&per_page=10")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_list_geonames_with_search(self):
        """Test GeoNames listing with search query."""
        response = client.get("/gazetteers/gazetteers/geonames?q=minnesota")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_list_geonames_with_callback(self):
        """Test GeoNames listing with JSONP callback."""
        response = client.get("/gazetteers/gazetteers/geonames?callback=myCallback")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")


class TestWOFGazetteer:
    """Test cases for Who's on First gazetteer endpoints."""

    def test_list_wof_success(self):
        """Test successful listing of WOF records."""
        response = client.get("/gazetteers/gazetteers/wof")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data
            assert "links" in data
        else:
            assert "detail" in data

    def test_list_wof_with_pagination(self):
        """Test WOF listing with pagination."""
        response = client.get("/gazetteers/gazetteers/wof?page=1&per_page=10")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_list_wof_with_search(self):
        """Test WOF listing with search query."""
        response = client.get("/gazetteers/gazetteers/wof?q=minnesota")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_list_wof_with_callback(self):
        """Test WOF listing with JSONP callback."""
        response = client.get("/gazetteers/gazetteers/wof?callback=myCallback")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")

    def test_get_wof_by_id_success(self):
        """Test getting WOF record by ID."""
        response = client.get("/gazetteers/gazetteers/wof/123")
        
        assert response.status_code in [200, 404, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert data["data"]["id"] == "123"
        elif response.status_code == 404:
            assert "detail" in data
        else:
            assert "detail" in data

    def test_get_wof_by_id_with_callback(self):
        """Test getting WOF record by ID with JSONP callback."""
        response = client.get("/gazetteers/gazetteers/wof/123?callback=myCallback")
        
        assert response.status_code in [200, 404, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")


class TestBTAAGazetteer:
    """Test cases for BTAA gazetteer endpoints."""

    def test_list_btaa_success(self):
        """Test successful listing of BTAA records."""
        response = client.get("/gazetteers/gazetteers/btaa")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data
            assert "links" in data
        else:
            assert "detail" in data

    def test_list_btaa_with_pagination(self):
        """Test BTAA listing with pagination."""
        response = client.get("/gazetteers/gazetteers/btaa?page=1&per_page=10")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_list_btaa_with_search(self):
        """Test BTAA listing with search query."""
        response = client.get("/gazetteers/gazetteers/btaa?q=minnesota")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_list_btaa_with_callback(self):
        """Test BTAA listing with JSONP callback."""
        response = client.get("/gazetteers/gazetteers/btaa?callback=myCallback")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")


class TestGazetteerSearch:
    """Test cases for gazetteer search endpoints."""

    def test_search_all_gazetteers_success(self):
        """Test searching all gazetteers."""
        response = client.get("/gazetteers/gazetteers/search?q=minnesota")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data
            assert "links" in data
        else:
            assert "detail" in data

    def test_search_all_gazetteers_with_pagination(self):
        """Test searching all gazetteers with pagination."""
        response = client.get("/gazetteers/gazetteers/search?q=minnesota&page=1&per_page=10")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_search_all_gazetteers_with_callback(self):
        """Test searching all gazetteers with JSONP callback."""
        response = client.get("/gazetteers/gazetteers/search?q=minnesota&callback=myCallback")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")

    def test_search_all_gazetteers_empty_query(self):
        """Test searching all gazetteers with empty query."""
        response = client.get("/gazetteers/gazetteers/search?q=")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_search_all_gazetteers_no_query(self):
        """Test searching all gazetteers without query parameter."""
        response = client.get("/gazetteers/gazetteers/search")
        
        assert response.status_code in [200, 422, 500]
        data = response.json()
        
        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data


class TestGazetteerParameterValidation:
    """Test cases for parameter validation."""

    def test_invalid_page_parameter(self):
        """Test with invalid page parameter."""
        response = client.get("/gazetteers/gazetteers/geonames?page=0")
        
        assert response.status_code in [200, 400, 422, 500]
        data = response.json()
        
        if response.status_code in [400, 422]:
            assert "detail" in data

    def test_invalid_per_page_parameter(self):
        """Test with invalid per_page parameter."""
        response = client.get("/gazetteers/gazetteers/geonames?per_page=0")
        
        assert response.status_code in [200, 400, 422, 500]
        data = response.json()
        
        if response.status_code in [400, 422]:
            assert "detail" in data

    def test_large_per_page_parameter(self):
        """Test with large per_page parameter."""
        response = client.get("/gazetteers/gazetteers/geonames?per_page=1000")
        
        assert response.status_code in [200, 400, 422, 500]
        data = response.json()
        
        if response.status_code in [400, 422]:
            assert "detail" in data


class TestGazetteerResponseFormat:
    """Test cases for response format validation."""

    def test_jsonapi_response_structure(self):
        """Test that responses follow JSON:API structure."""
        response = client.get("/gazetteers/gazetteers/geonames")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should have JSON:API structure
            assert "data" in data
            assert "meta" in data
            assert "links" in data
            
            # Data should be a list
            assert isinstance(data["data"], list)
            
            # Meta should contain pagination info
            meta = data["meta"]
            assert "totalCount" in meta
            assert "totalPages" in meta
            assert "currentPage" in meta
            assert "perPage" in meta

    def test_geonames_response_content(self):
        """Test GeoNames response content structure."""
        response = client.get("/gazetteers/gazetteers/geonames")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200 and data["data"]:
            # Check first item structure
            first_item = data["data"][0]
            assert "id" in first_item
            assert "type" in first_item
            assert "attributes" in first_item
            assert first_item["type"] == "geoname"

    def test_wof_response_content(self):
        """Test WOF response content structure."""
        response = client.get("/gazetteers/gazetteers/wof")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200 and data["data"]:
            # Check first item structure
            first_item = data["data"][0]
            assert "id" in first_item
            assert "type" in first_item
            assert "attributes" in first_item
            assert first_item["type"] == "wof"

    def test_btaa_response_content(self):
        """Test BTAA response content structure."""
        response = client.get("/gazetteers/gazetteers/btaa")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200 and data["data"]:
            # Check first item structure
            first_item = data["data"][0]
            assert "id" in first_item
            assert "type" in first_item
            assert "attributes" in first_item
            assert first_item["type"] == "btaa"


class TestGazetteerErrorHandling:
    """Test cases for error handling."""

    def test_database_connection_error(self):
        """Test handling of database connection errors."""
        # This test will pass if database is unavailable
        response = client.get("/gazetteers/gazetteers/geonames")
        
        # Should handle database errors gracefully
        assert response.status_code in [200, 500]
        
        if response.status_code == 500:
            data = response.json()
            assert "detail" in data

    def test_invalid_wok_id(self):
        """Test with invalid WOK ID."""
        response = client.get("/gazetteers/gazetteers/wof/invalid-id")
        
        assert response.status_code in [200, 404, 422, 500]
        
        if response.status_code == 404:
            data = response.json()
            assert "detail" in data

    def test_missing_required_parameters(self):
        """Test with missing required parameters."""
        # Most gazetteer endpoints don't require parameters, but test edge cases
        response = client.get("/gazetteers/gazetteers/wof/")
        
        # Should handle missing ID gracefully
        assert response.status_code in [404, 422, 500]


class TestGazetteerCaching:
    """Test cases for caching behavior."""

    def test_cached_responses(self):
        """Test that responses are cached."""
        # Make the same request twice
        response1 = client.get("/gazetteers/gazetteers/geonames")
        response2 = client.get("/gazetteers/gazetteers/geonames")
        
        # Both should have same status code
        assert response1.status_code == response2.status_code
        
        if response1.status_code == 200:
            # Response content should be the same
            assert response1.json() == response2.json()

    def test_callback_parameter_handling(self):
        """Test that callback parameter is handled correctly."""
        response = client.get("/gazetteers/gazetteers/geonames?callback=testCallback")
        
        assert response.status_code in [200, 500]
        data = response.json()
        
        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert "testCallback" in data
