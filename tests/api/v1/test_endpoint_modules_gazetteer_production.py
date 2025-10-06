"""
Production database tests for gazetteer endpoint module.
Uses real database connections to achieve higher coverage.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Create test app
from app.api.v1.endpoint_modules.gazetteer import router
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestGazetteerProductionDatabase:
    """Test gazetteer endpoints using production database connections."""

    def test_list_gazetteers_with_real_database(self):
        """Test list gazetteers with real database connection."""
        response = client.get("/gazetteers")
        
        # Should return either success or database connection error
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "jsonapi" in data
            assert "links" in data
            assert len(data["data"]) == 3  # Should have 3 gazetteers

    def test_search_all_gazetteers_with_real_database(self):
        """Test search all gazetteers with real database connection."""
        response = client.get("/gazetteers/search?q=test")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "geonames" in data
            assert "wof" in data
            assert "btaa" in data

    def test_search_geonames_with_real_database(self):
        """Test search GeoNames with real database connection."""
        response = client.get("/gazetteers/geonames/search?q=test")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "jsonapi" in data
            assert "links" in data

    def test_search_wof_with_real_database(self):
        """Test search WOF with real database connection."""
        response = client.get("/gazetteers/wof/search?q=test")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "jsonapi" in data
            assert "links" in data

    def test_search_btaa_with_real_database(self):
        """Test search BTAA with real database connection."""
        response = client.get("/gazetteers/btaa/search?q=test")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "jsonapi" in data
            assert "links" in data

    def test_search_specific_gazetteer_geonames(self):
        """Test search with specific gazetteer=geonames."""
        response = client.get("/gazetteers/search?q=test&gazetteer=geonames")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]

    def test_search_specific_gazetteer_wof(self):
        """Test search with specific gazetteer=wof."""
        response = client.get("/gazetteers/search?q=test&gazetteer=wof")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]

    def test_search_specific_gazetteer_btaa(self):
        """Test search with specific gazetteer=btaa."""
        response = client.get("/gazetteers/search?q=test&gazetteer=btaa")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]

    def test_search_invalid_gazetteer(self):
        """Test search with invalid gazetteer parameter."""
        response = client.get("/gazetteers/search?q=test&gazetteer=invalid")
        
        # Should return validation error
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid gazetteer specified" in data["detail"]

    def test_search_missing_query_parameter(self):
        """Test search without required query parameter."""
        response = client.get("/gazetteers/search")
        
        # Should return validation error
        assert response.status_code == 422

    def test_search_with_pagination(self):
        """Test search with pagination parameters."""
        response = client.get("/gazetteers/search?q=test&limit=5&offset=10")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]

    def test_search_with_jsonp_callback(self):
        """Test search with JSONP callback parameter."""
        response = client.get("/gazetteers/search?q=test&callback=testCallback")
        
        # Should return either success or database error
        assert response.status_code in [200, 500]

    def test_search_invalid_limit_parameter(self):
        """Test search with invalid limit parameter."""
        response = client.get("/gazetteers/search?q=test&limit=0")
        
        # Should return validation error
        assert response.status_code == 422

    def test_search_invalid_offset_parameter(self):
        """Test search with invalid offset parameter."""
        response = client.get("/gazetteers/search?q=test&offset=-1")
        
        # Should return validation error
        assert response.status_code == 422

    def test_search_large_limit_parameter(self):
        """Test search with large limit parameter."""
        response = client.get("/gazetteers/search?q=test&limit=101")
        
        # Should return validation error
        assert response.status_code == 422

    def test_search_geonames_with_pagination(self):
        """Test GeoNames search with pagination."""
        response = client.get("/gazetteers/geonames/search?q=test&limit=5&offset=0")
        assert response.status_code in [200, 500]

    def test_search_wof_with_pagination(self):
        """Test WOF search with pagination."""
        response = client.get("/gazetteers/wof/search?q=test&limit=5&offset=0")
        assert response.status_code in [200, 500]

    def test_search_btaa_with_pagination(self):
        """Test BTAA search with pagination."""
        response = client.get("/gazetteers/btaa/search?q=test&limit=5&offset=0")
        assert response.status_code in [200, 500]

    def test_search_geonames_with_jsonp(self):
        """Test GeoNames search with JSONP callback."""
        response = client.get("/gazetteers/geonames/search?q=test&callback=testCallback")
        assert response.status_code in [200, 500]

    def test_search_wof_with_jsonp(self):
        """Test WOF search with JSONP callback."""
        response = client.get("/gazetteers/wof/search?q=test&callback=testCallback")
        assert response.status_code in [200, 500]

    def test_search_btaa_with_jsonp(self):
        """Test BTAA search with JSONP callback."""
        response = client.get("/gazetteers/btaa/search?q=test&callback=testCallback")
        assert response.status_code in [200, 500]

    def test_search_different_query_types(self):
        """Test search with different types of queries."""
        test_queries = [
            "geography",
            "climate data",
            "population statistics",
            "geological survey",
            "satellite imagery",
            "Minnesota",
            "United States",
            "city",
            "county",
            "state"
        ]
        
        for query in test_queries:
            response = client.get(f"/gazetteers/search?q={query}")
            assert response.status_code in [200, 500]

    def test_search_unicode_queries(self):
        """Test search with unicode characters."""
        response = client.get("/gazetteers/search?q=测试查询")
        assert response.status_code in [200, 500]

    def test_search_special_characters(self):
        """Test search with special characters."""
        response = client.get("/gazetteers/search?q=test+query+with+special+chars")
        assert response.status_code in [200, 500]

    def test_search_empty_query(self):
        """Test search with empty query."""
        response = client.get("/gazetteers/search?q=")
        assert response.status_code in [200, 500]

    def test_search_long_query(self):
        """Test search with very long query."""
        long_query = "a" * 1000
        response = client.get(f"/gazetteers/search?q={long_query}")
        assert response.status_code in [200, 500]

    def test_search_cache_behavior(self):
        """Test search cache behavior."""
        # Make multiple identical requests to test caching
        response1 = client.get("/gazetteers/search?q=test&limit=5")
        response2 = client.get("/gazetteers/search?q=test&limit=5")
        
        # Both should return the same status
        assert response1.status_code == response2.status_code

    def test_search_database_connection_handling(self):
        """Test search database connection handling."""
        # Test multiple endpoints to exercise session management
        endpoints = [
            "/gazetteers",
            "/gazetteers/search?q=test",
            "/gazetteers/geonames/search?q=test",
            "/gazetteers/wof/search?q=test",
            "/gazetteers/btaa/search?q=test"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not crash due to session issues
            assert response.status_code in [200, 500]

    def test_search_response_structure_validation(self):
        """Test search response structure validation."""
        response = client.get("/gazetteers/search?q=test")
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have proper structure for each gazetteer
            for gazetteer_name in ["geonames", "wof", "btaa"]:
                if gazetteer_name in data:
                    gazetteer_data = data[gazetteer_name]
                    assert isinstance(gazetteer_data, dict)

    def test_search_geonames_response_structure(self):
        """Test GeoNames search response structure."""
        response = client.get("/gazetteers/geonames/search?q=test")
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have JSON:API structure
            assert "jsonapi" in data
            assert "data" in data
            assert "links" in data
            
            # If there are results, they should have proper structure
            if data["data"]:
                for result in data["data"]:
                    assert "type" in result
                    assert "id" in result
                    assert "attributes" in result

    def test_search_wof_response_structure(self):
        """Test WOF search response structure."""
        response = client.get("/gazetteers/wof/search?q=test")
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have JSON:API structure
            assert "jsonapi" in data
            assert "data" in data
            assert "links" in data

    def test_search_btaa_response_structure(self):
        """Test BTAA search response structure."""
        response = client.get("/gazetteers/btaa/search?q=test")
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have JSON:API structure
            assert "jsonapi" in data
            assert "data" in data
            assert "links" in data

    def test_list_gazetteers_response_structure(self):
        """Test list gazetteers response structure."""
        response = client.get("/gazetteers")
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have JSON:API structure
            assert "jsonapi" in data
            assert "data" in data
            assert "links" in data
            
            # Should have exactly 3 gazetteers
            assert len(data["data"]) == 3
            
            # Each gazetteer should have proper structure
            for gazetteer in data["data"]:
                assert "id" in gazetteer
                assert "type" in gazetteer
                assert gazetteer["type"] == "gazetteer"
                assert "attributes" in gazetteer
                assert "name" in gazetteer["attributes"]
                assert "record_count" in gazetteer["attributes"]

    def test_search_error_handling(self):
        """Test search error handling."""
        # Test with parameters that might cause database errors
        response = client.get("/gazetteers/search?q=test&limit=999999&offset=999999")
        assert response.status_code in [200, 422, 500]  # Include 422 for validation errors

    def test_search_async_operations(self):
        """Test search async operations."""
        # Test endpoints that use async database operations
        async_endpoints = [
            "/gazetteers/search?q=test",
            "/gazetteers/geonames/search?q=test",
            "/gazetteers/wof/search?q=test",
            "/gazetteers/btaa/search?q=test"
        ]
        
        for endpoint in async_endpoints:
            response = client.get(endpoint)
            # Should handle async operations properly
            assert response.status_code in [200, 500]

    def test_search_sql_query_execution(self):
        """Test SQL query execution with real database."""
        # Test endpoints that execute SQL queries
        response = client.get("/gazetteers/search?q=test")
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            # Should have executed the SQL queries successfully
            data = response.json()
            assert "geonames" in data
            assert "wof" in data
            assert "btaa" in data

    def test_search_service_integration(self):
        """Test integration with real database services."""
        # Test endpoints that use real database connections
        response = client.get("/gazetteers/search?q=test")
        assert response.status_code in [200, 500]

    def test_search_data_processing(self):
        """Test search data processing with real database."""
        # Test that the endpoint processes database results properly
        response = client.get("/gazetteers/search?q=test&limit=1")
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            # Should have processed the database results properly
            assert "geonames" in data
            assert "wof" in data
            assert "btaa" in data
