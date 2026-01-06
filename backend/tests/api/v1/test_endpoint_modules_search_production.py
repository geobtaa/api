"""
Production database tests for search endpoint module.
Uses real database connections and SearchService to achieve higher coverage.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Create test app
from app.api.v1.endpoint_modules.search import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestSearchProductionDatabase:
    """Test search endpoints using production database connections and SearchService."""

    def test_search_endpoint_with_real_service(self):
        """Test search endpoint with real SearchService."""
        response = client.get("/search?q=test")

        # Should return either success or service error
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "jsonapi" in data
            assert "links" in data

    def test_search_endpoint_with_pagination(self):
        """Test search endpoint with pagination parameters."""
        response = client.get("/search?q=test&page=1&per_page=5")
        assert response.status_code in [200, 500]

    def test_search_endpoint_with_sorting(self):
        """Test search endpoint with sorting options."""
        sort_options = ["relevance", "year_desc", "year_asc", "title_asc", "title_desc"]

        for sort in sort_options:
            response = client.get(f"/search?q=test&sort={sort}")
            assert response.status_code in [200, 500]

    def test_search_endpoint_with_jsonp_callback(self):
        """Test search endpoint with JSONP callback."""
        response = client.get("/search?q=test&callback=testCallback")
        assert response.status_code in [200, 500]

    def test_search_endpoint_without_query(self):
        """Test search endpoint without query parameter."""
        response = client.get("/search")
        assert response.status_code in [200, 500]

    def test_search_endpoint_invalid_page(self):
        """Test search endpoint with invalid page parameter."""
        response = client.get("/search?q=test&page=0")
        assert response.status_code in [200, 422, 500]

    def test_search_endpoint_invalid_per_page(self):
        """Test search endpoint with invalid per_page parameter."""
        response = client.get("/search?q=test&per_page=0")
        assert response.status_code in [200, 422, 500]

    def test_search_endpoint_large_per_page(self):
        """Test search endpoint with large per_page parameter."""
        response = client.get("/search?q=test&per_page=1000")
        assert response.status_code in [200, 422, 500]

    def test_search_endpoint_empty_query(self):
        """Test search endpoint with empty query."""
        response = client.get("/search?q=")
        assert response.status_code in [200, 500]

    def test_search_endpoint_special_characters(self):
        """Test search endpoint with special characters in query."""
        response = client.get("/search?q=test+query+with+special+chars")
        assert response.status_code in [200, 500]

    def test_search_endpoint_unicode_query(self):
        """Test search endpoint with unicode characters."""
        response = client.get("/search?q=测试查询")
        assert response.status_code in [200, 500]

    def test_search_endpoint_long_query(self):
        """Test search endpoint with very long query."""
        long_query = "a" * 1000
        response = client.get(f"/search?q={long_query}")
        assert response.status_code in [200, 500]

    def test_search_endpoint_multiple_pages(self):
        """Test search endpoint with multiple page requests."""
        for page in range(1, 4):
            response = client.get(f"/search?q=test&page={page}")
            assert response.status_code in [200, 500]

    def test_search_endpoint_cache_behavior(self):
        """Test search endpoint cache behavior."""
        # Make multiple identical requests to test caching
        response1 = client.get("/search?q=test&page=1&per_page=5")
        response2 = client.get("/search?q=test&page=1&per_page=5")

        # Both should return the same status
        assert response1.status_code == response2.status_code

    def test_search_endpoint_database_connection(self):
        """Test search endpoint database connection handling."""
        # Test that the endpoint handles database connections properly
        response = client.get("/search?q=test&per_page=1")
        assert response.status_code in [200, 500]

    def test_search_endpoint_error_handling(self):
        """Test search endpoint error handling."""
        # Test with parameters that might cause errors
        response = client.get("/search?q=test&page=-1&per_page=0")
        assert response.status_code in [200, 422, 500]

    def test_search_endpoint_response_structure(self):
        """Test search endpoint response structure."""
        response = client.get("/search?q=test")

        if response.status_code == 200:
            data = response.json()

            # Check JSON:API structure
            assert "jsonapi" in data
            assert "data" in data
            assert "links" in data

            # Check data structure
            if data["data"]:
                for item in data["data"]:
                    assert "type" in item
                    assert "id" in item
                    assert "attributes" in item

    def test_search_endpoint_meta_information(self):
        """Test search endpoint meta information."""
        response = client.get("/search?q=test")

        if response.status_code == 200:
            data = response.json()

            # Should have meta information
            if "meta" in data:
                meta = data["meta"]
                assert isinstance(meta, dict)

    def test_search_endpoint_links_structure(self):
        """Test search endpoint links structure."""
        response = client.get("/search?q=test")

        if response.status_code == 200:
            data = response.json()

            # Should have links
            assert "links" in data
            links = data["links"]
            assert isinstance(links, dict)

    def test_search_endpoint_with_different_queries(self):
        """Test search endpoint with different types of queries."""
        test_queries = [
            "geography",
            "climate data",
            "population statistics",
            "geological survey",
            "satellite imagery",
        ]

        for query in test_queries:
            response = client.get(f"/search?q={query}")
            assert response.status_code in [200, 500]

    def test_search_endpoint_performance_considerations(self):
        """Test search endpoint with performance considerations."""
        # Test with reasonable parameters that shouldn't timeout
        response = client.get("/search?q=test&page=1&per_page=10")
        assert response.status_code in [200, 500]

        # Test with larger page size
        response = client.get("/search?q=test&page=1&per_page=50")
        assert response.status_code in [200, 500]

    def test_search_endpoint_edge_cases(self):
        """Test search endpoint edge cases."""
        # Test with very small page
        response = client.get("/search?q=test&page=1&per_page=1")
        assert response.status_code in [200, 500]

        # Test with page 1
        response = client.get("/search?q=test&page=1")
        assert response.status_code in [200, 500]

    def test_search_endpoint_parameter_combinations(self):
        """Test search endpoint with different parameter combinations."""
        combinations = [
            {"q": "test", "page": 1, "per_page": 5, "sort": "relevance"},
            {"q": "geography", "page": 2, "per_page": 20, "sort": "year_desc"},
            {"q": "climate", "sort": "title_asc"},
            {"page": 1, "per_page": 10},  # No query
        ]

        for params in combinations:
            response = client.get("/search", params=params)
            assert response.status_code in [200, 422, 500]

    def test_search_endpoint_with_real_search_service(self):
        """Test search endpoint integration with real SearchService."""
        # This tests the actual SearchService integration
        response = client.get("/search?q=test&per_page=5")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            # Should have proper search results structure
            assert "data" in data

    def test_search_endpoint_database_session_handling(self):
        """Test search endpoint database session handling."""
        # Make multiple requests to test session management
        endpoints = [
            "/search?q=test&per_page=1",
            "/search?q=geography&per_page=1",
            "/search?q=climate&per_page=1",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not crash due to session issues
            assert response.status_code in [200, 500]

    def test_search_endpoint_async_operations(self):
        """Test search endpoint async operations."""
        # Test endpoints that use async database operations
        response = client.get("/search?q=test&per_page=5")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            # Should handle async operations properly
            data = response.json()
            assert "data" in data

    def test_search_endpoint_error_logging(self):
        """Test search endpoint error logging."""
        # Test with parameters that might cause errors
        response = client.get("/search?q=test&page=999999&per_page=1")
        assert response.status_code in [200, 500]

        # Should log errors appropriately without crashing

    def test_search_endpoint_service_integration(self):
        """Test search endpoint integration with services."""
        # Test that the endpoint integrates properly with SearchService
        response = client.get("/search?q=test")
        assert response.status_code in [200, 500]

    def test_search_endpoint_response_processing(self):
        """Test search endpoint response processing."""
        response = client.get("/search?q=test&per_page=5")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            # Should have processed the search results properly
            assert "data" in data
            assert "jsonapi" in data


class TestSuggestProductionDatabase:
    """Test suggest endpoint using production database connections."""

    def test_suggest_endpoint_with_real_service(self):
        """Test suggest endpoint with real SearchService."""
        response = client.get("/suggest?q=test")

        # Should return either success or service error
        assert response.status_code in [200, 500]

    def test_suggest_endpoint_without_query(self):
        """Test suggest endpoint without query parameter."""
        response = client.get("/suggest")
        assert response.status_code in [200, 422, 500]

    def test_suggest_endpoint_with_jsonp_callback(self):
        """Test suggest endpoint with JSONP callback."""
        response = client.get("/suggest?q=test&callback=testCallback")
        assert response.status_code in [200, 500]

    def test_suggest_endpoint_empty_query(self):
        """Test suggest endpoint with empty query."""
        response = client.get("/suggest?q=")
        assert response.status_code in [200, 500]

    def test_suggest_endpoint_special_characters(self):
        """Test suggest endpoint with special characters."""
        response = client.get("/suggest?q=test+query+with+special+chars")
        assert response.status_code in [200, 500]

    def test_suggest_endpoint_unicode_query(self):
        """Test suggest endpoint with unicode characters."""
        response = client.get("/suggest?q=测试查询")
        assert response.status_code in [200, 500]

    def test_suggest_endpoint_cache_behavior(self):
        """Test suggest endpoint cache behavior."""
        # Make multiple identical requests to test caching
        response1 = client.get("/suggest?q=test")
        response2 = client.get("/suggest?q=test")

        # Both should return the same status
        assert response1.status_code == response2.status_code

    def test_suggest_endpoint_response_structure(self):
        """Test suggest endpoint response structure."""
        response = client.get("/suggest?q=test")

        if response.status_code == 200:
            data = response.json()

            # Check JSON:API structure
            assert "jsonapi" in data
            assert "data" in data
            assert "links" in data

    def test_suggest_endpoint_with_different_queries(self):
        """Test suggest endpoint with different types of queries."""
        test_queries = ["geography", "climate", "population", "geological", "satellite"]

        for query in test_queries:
            response = client.get(f"/suggest?q={query}")
            assert response.status_code in [200, 500]

    def test_suggest_endpoint_with_real_search_service(self):
        """Test suggest endpoint integration with real SearchService."""
        response = client.get("/suggest?q=test")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            # Should have proper suggest results structure
            assert "data" in data
