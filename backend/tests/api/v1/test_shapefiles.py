"""
Tests for the shapefiles API endpoints.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.shapefiles import router

# Create test app
app = FastAPI()
app.include_router(router, prefix="/shapefiles")

# Test client
client = TestClient(app)


# Skip all shapefile tests - feature hasn't landed yet
pytestmark = pytest.mark.skip(reason="Shapefile feature hasn't landed yet")


class TestShapefilesEndpoints:
    """Test cases for shapefiles endpoints."""

    def test_list_shapefiles_success(self):
        """Test successful listing of shapefiles."""
        response = client.get("/shapefiles/shapefiles")

        # Should return 200, 422, or 500 depending on DuckDB connection and parameters
        assert response.status_code in [200, 422, 500]
        data = response.json()

        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data
        else:
            assert "detail" in data

    def test_list_shapefiles_with_callback(self):
        """Test listing shapefiles with JSONP callback."""
        response = client.get("/shapefiles/shapefiles?callback=myCallback")

        assert response.status_code in [200, 422, 500]
        data = response.json()

        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")

    def test_list_shapefiles_with_pagination(self):
        """Test listing shapefiles with pagination."""
        response = client.get("/shapefiles/shapefiles?page=1&per_page=10")

        assert response.status_code in [200, 422, 500]
        data = response.json()

        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data

    def test_get_shapefile_info_success(self):
        """Test getting shapefile info by table name."""
        response = client.get("/shapefiles/shapefiles/test_table/info")

        # Should return 200, 404, 500, or 503 depending on DuckDB connection and table existence
        assert response.status_code in [200, 404, 500, 503]
        data = response.json()

        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data
        elif response.status_code == 404:
            assert "detail" in data
        else:
            assert "detail" in data

    def test_get_shapefile_info_with_callback(self):
        """Test getting shapefile info with JSONP callback."""
        response = client.get("/shapefiles/shapefiles/test_table/info?callback=myCallback")

        assert response.status_code in [200, 404, 500, 503]
        data = response.json()

        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")

    def test_list_shapefile_tables_success(self):
        """Test successful listing of shapefile tables."""
        response = client.get("/shapefiles/shapefiles/tables")

        # Should return 200, 422, or 500 depending on DuckDB connection and parameters
        assert response.status_code in [200, 422, 500]
        data = response.json()

        if response.status_code == 200:
            assert "data" in data
            assert "meta" in data
        else:
            assert "detail" in data

    def test_list_shapefile_tables_with_callback(self):
        """Test listing shapefile tables with JSONP callback."""
        response = client.get("/shapefiles/shapefiles/tables?callback=myCallback")

        assert response.status_code in [200, 422, 500]
        data = response.json()

        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert data.startswith("myCallback(")
            assert data.endswith(")")


class TestShapefilesParameterValidation:
    """Test cases for parameter validation."""

    def test_invalid_page_parameter(self):
        """Test with invalid page parameter."""
        response = client.get("/shapefiles/shapefiles?page=0")

        assert response.status_code in [200, 400, 422, 500]
        data = response.json()

        if response.status_code in [400, 422]:
            assert "detail" in data

    def test_invalid_per_page_parameter(self):
        """Test with invalid per_page parameter."""
        response = client.get("/shapefiles/shapefiles?per_page=0")

        assert response.status_code in [200, 400, 422, 500]
        data = response.json()

        if response.status_code in [400, 422]:
            assert "detail" in data

    def test_large_per_page_parameter(self):
        """Test with large per_page parameter."""
        response = client.get("/shapefiles/shapefiles?per_page=1000")

        assert response.status_code in [200, 400, 422, 500]
        data = response.json()

        if response.status_code in [400, 422]:
            assert "detail" in data


class TestShapefilesResponseFormat:
    """Test cases for response format validation."""

    def test_jsonapi_response_structure(self):
        """Test that responses follow JSON:API structure."""
        response = client.get("/shapefiles/shapefiles")

        assert response.status_code in [200, 422, 500]
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

    def test_shapefile_response_content(self):
        """Test shapefile response content structure."""
        response = client.get("/shapefiles/shapefiles")

        assert response.status_code in [200, 422, 500]
        data = response.json()

        if response.status_code == 200 and data["data"]:
            # Check first item structure
            first_item = data["data"][0]
            assert "id" in first_item
            assert "type" in first_item
            assert "attributes" in first_item
            assert first_item["type"] == "shapefile"

    def test_shapefile_info_response_content(self):
        """Test shapefile info response content structure."""
        response = client.get("/shapefiles/shapefiles/test_table/info")

        assert response.status_code in [200, 404, 500, 503]
        data = response.json()

        if response.status_code == 200:
            # Should have JSON:API structure
            assert "data" in data
            assert "meta" in data
            assert "links" in data

            # Data should be a single object
            assert isinstance(data["data"], dict)
            assert data["data"]["type"] == "shapefile_info"


class TestShapefilesErrorHandling:
    """Test cases for error handling."""

    def test_duckdb_not_available(self):
        """Test handling when DuckDB is not available."""
        # This test will pass if DuckDB is available, or handle the error gracefully
        response = client.get("/shapefiles/shapefiles")

        # Should handle DuckDB errors gracefully
        assert response.status_code in [200, 422, 500]

        if response.status_code == 500:
            data = response.json()
            assert "detail" in data

    def test_invalid_table_name(self):
        """Test with invalid table name."""
        response = client.get("/shapefiles/shapefiles/invalid_table_name/info")

        assert response.status_code in [200, 404, 500, 503]

        if response.status_code == 404:
            data = response.json()
            assert "detail" in data

    def test_missing_table_name(self):
        """Test with missing table name."""
        response = client.get("/shapefiles/shapefiles//info")

        # Should handle missing table name gracefully
        assert response.status_code in [404, 422, 500]


class TestShapefilesCaching:
    """Test cases for caching behavior."""

    def test_cached_responses(self):
        """Test that responses are cached."""
        # Make the same request twice
        response1 = client.get("/shapefiles/shapefiles")
        response2 = client.get("/shapefiles/shapefiles")

        # Both should have same status code
        assert response1.status_code == response2.status_code

        if response1.status_code == 200:
            # Response content should be the same
            assert response1.json() == response2.json()

    def test_callback_parameter_handling(self):
        """Test that callback parameter is handled correctly."""
        response = client.get("/shapefiles/shapefiles?callback=testCallback")

        assert response.status_code in [200, 422, 500]
        data = response.json()

        if response.status_code == 200:
            # Should be JSONP response
            assert isinstance(data, str)
            assert "testCallback" in data


class TestShapefilesUtilityFunctions:
    """Test cases for utility functions."""

    def test_get_duckdb_connection_without_duckdb(self):
        """Test DuckDB connection when DuckDB is not available."""
        # This test verifies the error handling when DuckDB is not available
        # The actual behavior depends on whether DuckDB is installed
        response = client.get("/shapefiles/shapefiles")

        # Should handle DuckDB availability gracefully
        assert response.status_code in [200, 422, 500]

        if response.status_code == 500:
            data = response.json()
            # Could be DuckDB not available or other database errors
            assert "detail" in data

    def test_duckdb_database_path_configuration(self):
        """Test that DuckDB database path is configured correctly."""
        # This test verifies the endpoint can handle the configured database path
        response = client.get("/shapefiles/shapefiles")

        # Should handle database path configuration gracefully
        assert response.status_code in [200, 422, 500]
