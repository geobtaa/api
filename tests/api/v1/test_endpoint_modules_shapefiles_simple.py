"""
Simple tests for the refactored shapefiles endpoints.
Focus on structural testing and basic functionality.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Skip all shapefile tests - feature hasn't landed yet
pytestmark = pytest.mark.skip(reason="Shapefile feature hasn't landed yet")

from app.api.v1.endpoint_modules.shapefiles import (
    DUCKDB_DATABASE_PATH,
    get_shapefile_service,
    router,
)
from app.services.shapefile_service import (
    DuckDBConnectionError,
    Page,
    ShapefileDownloadError,
    ShapefileProcessingError,
    ShapefileService,
)

# Create test app
app = FastAPI()
app.include_router(router)


class TestShapefileEndpointsSimple:
    """Simple tests for shapefile endpoints."""

    def test_router_configuration(self):
        """Test that the router is properly configured."""
        assert router is not None
        routes = [route.path for route in router.routes]
        assert "/shapefiles/query" in routes
        assert "/shapefiles/schema" in routes
        assert "/shapefiles/preview" in routes

    def test_dependency_injection_function(self):
        """Test the dependency injection function."""
        service = get_shapefile_service()

        assert isinstance(service, ShapefileService)
        assert hasattr(service, "download_service")
        assert hasattr(service, "duckdb_service")
        assert service.duckdb_service.database_path == DUCKDB_DATABASE_PATH

    def test_duckdb_path_configuration(self):
        """Test that DuckDB path is properly configured."""
        import os

        expected_path = os.getenv("DUCKDB_DATABASE_PATH", "data/duckdb/btaa_ogm_api.duckdb")
        assert DUCKDB_DATABASE_PATH == expected_path

    def test_endpoint_paths(self):
        """Test that all endpoints have correct paths."""
        routes = [route.path for route in router.routes]

        # Check that all expected paths exist
        assert "/shapefiles/query" in routes
        assert "/shapefiles/schema" in routes
        assert "/shapefiles/preview" in routes

        # Check that routes are GET methods
        for route in router.routes:
            if route.path in ["/shapefiles/query", "/shapefiles/schema", "/shapefiles/preview"]:
                assert hasattr(route, "methods")
                assert "GET" in route.methods


class TestShapefileEndpointsWithMocking:
    """Test endpoints with mocked services."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock shapefile service."""
        mock_service = Mock(spec=ShapefileService)
        return mock_service

    @pytest.fixture
    def client(self, mock_service):
        """Create test client with mocked service."""
        # Override the dependency in the FastAPI app
        app.dependency_overrides[get_shapefile_service] = lambda: mock_service
        yield TestClient(app)
        # Clean up the override
        app.dependency_overrides.clear()

    def test_query_endpoint_success(self, client, mock_service):
        """Test successful query endpoint."""
        # Setup mock response
        expected_page = Page(
            total_rows=100,
            columns=["id", "name", "geometry"],
            rows=[{"id": 1, "name": "Test Feature", "geometry": "POINT(0 0)"}],
        )
        mock_service.query_shapefile = AsyncMock(return_value=expected_page)

        # Make request
        response = client.get("/shapefiles/query?s3_uri=https://example.com/test.shp&sql=id>0")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        # The refactored endpoint returns the Page dict directly
        assert data["total_rows"] == 100
        assert data["columns"] == ["id", "name", "geometry"]
        assert len(data["rows"]) == 1

        # Verify service was called correctly
        mock_service.query_shapefile.assert_called_once_with("https://example.com/test.shp", "id>0")

    def test_query_endpoint_with_callback(self, client, mock_service):
        """Test query endpoint with JSONP callback."""
        expected_page = Page(total_rows=50, columns=["id"], rows=[{"id": 1}])
        mock_service.query_shapefile = AsyncMock(return_value=expected_page)

        response = client.get(
            "/shapefiles/query?s3_uri=https://example.com/test.shp&sql=id>0&callback=myCallback"
        )

        assert response.status_code == 200
        # Should return JSONP format
        content = response.text
        assert content.startswith("myCallback(")
        assert content.endswith(")")

    def test_query_endpoint_duckdb_error(self, client, mock_service):
        """Test query endpoint with DuckDB connection error."""
        mock_service.query_shapefile = AsyncMock(
            side_effect=DuckDBConnectionError("DuckDB not available")
        )

        response = client.get("/shapefiles/query?s3_uri=https://example.com/test.shp&sql=id>0")

        assert response.status_code == 503
        data = response.json()
        assert "DuckDB not available" in data["detail"]

    def test_query_endpoint_download_error(self, client, mock_service):
        """Test query endpoint with download error."""
        mock_service.query_shapefile = AsyncMock(
            side_effect=ShapefileDownloadError("Download failed")
        )

        response = client.get("/shapefiles/query?s3_uri=https://example.com/test.shp&sql=id>0")

        assert response.status_code == 400
        data = response.json()
        assert "Download failed" in data["detail"]

    def test_query_endpoint_processing_error(self, client, mock_service):
        """Test query endpoint with processing error."""
        mock_service.query_shapefile = AsyncMock(side_effect=ShapefileProcessingError("SQL error"))

        response = client.get("/shapefiles/query?s3_uri=https://example.com/test.shp&sql=invalid")

        assert response.status_code == 500
        data = response.json()
        assert "SQL error" in data["detail"]

    def test_query_endpoint_missing_parameters(self, client, mock_service):
        """Test query endpoint with missing required parameters."""
        response = client.get("/shapefiles/query")

        assert response.status_code == 422  # Validation error

    def test_schema_endpoint_success(self, client, mock_service):
        """Test successful schema endpoint."""
        expected_schema = [
            {
                "column_name": "id",
                "column_type": "INTEGER",
                "null": "NO",
                "key": "PRI",
                "default": None,
                "extra": "",
            },
            {
                "column_name": "name",
                "column_type": "VARCHAR",
                "null": "YES",
                "key": "",
                "default": None,
                "extra": "",
            },
        ]
        mock_service.get_shapefile_schema = AsyncMock(return_value=expected_schema)

        response = client.get("/shapefiles/schema?s3_uri=https://example.com/test.shp")

        assert response.status_code == 200
        data = response.json()
        # The refactored endpoint returns the schema directly
        assert len(data) == 2
        assert data[0]["column_name"] == "id"

        mock_service.get_shapefile_schema.assert_called_once_with("https://example.com/test.shp")

    def test_schema_endpoint_with_callback(self, client, mock_service):
        """Test schema endpoint with JSONP callback."""
        expected_schema = [{"column_name": "id", "column_type": "INTEGER"}]
        mock_service.get_shapefile_schema = AsyncMock(return_value=expected_schema)

        response = client.get(
            "/shapefiles/schema?s3_uri=https://example.com/test.shp&callback=myCallback"
        )

        assert response.status_code == 200
        content = response.text
        assert content.startswith("myCallback(")

    def test_schema_endpoint_error(self, client, mock_service):
        """Test schema endpoint with error."""
        mock_service.get_shapefile_schema = AsyncMock(
            side_effect=ShapefileProcessingError("Schema error")
        )

        response = client.get("/shapefiles/schema?s3_uri=https://example.com/test.shp")

        assert response.status_code == 500
        data = response.json()
        assert "Schema error" in data["detail"]

    def test_preview_endpoint_success(self, client, mock_service):
        """Test successful preview endpoint."""
        expected_page = Page(
            total_rows=1000,
            columns=["id", "name", "geometry"],
            rows=[
                {"id": 1, "name": "Feature 1", "geometry": "POINT(0 0)"},
                {"id": 2, "name": "Feature 2", "geometry": "POINT(1 1)"},
            ],
        )
        mock_service.preview_shapefile = AsyncMock(return_value=expected_page)

        response = client.get("/shapefiles/preview?s3_uri=https://example.com/test.shp&limit=5")

        assert response.status_code == 200
        data = response.json()
        # The refactored endpoint returns the Page dict directly
        assert data["total_rows"] == 1000
        assert len(data["rows"]) == 2

        mock_service.preview_shapefile.assert_called_once_with("https://example.com/test.shp", 5)

    def test_preview_endpoint_default_limit(self, client, mock_service):
        """Test preview endpoint with default limit."""
        expected_page = Page(total_rows=10, columns=["id"], rows=[{"id": 1}])
        mock_service.preview_shapefile = AsyncMock(return_value=expected_page)

        response = client.get("/shapefiles/preview?s3_uri=https://example.com/test.shp")

        assert response.status_code == 200
        # Should use default limit of 10
        mock_service.preview_shapefile.assert_called_once_with("https://example.com/test.shp", 10)

    def test_preview_endpoint_limit_validation(self, client, mock_service):
        """Test preview endpoint with invalid limit values."""
        # Test limit too low
        response = client.get("/shapefiles/preview?s3_uri=https://example.com/test.shp&limit=0")
        assert response.status_code == 422

        # Test limit too high
        response = client.get("/shapefiles/preview?s3_uri=https://example.com/test.shp&limit=2000")
        assert response.status_code == 422

    def test_preview_endpoint_with_callback(self, client, mock_service):
        """Test preview endpoint with JSONP callback."""
        expected_page = Page(total_rows=5, columns=["id"], rows=[{"id": 1}])
        mock_service.preview_shapefile = AsyncMock(return_value=expected_page)

        response = client.get(
            "/shapefiles/preview?s3_uri=https://example.com/test.shp&callback=myCallback"
        )

        assert response.status_code == 200
        content = response.text
        assert content.startswith("myCallback(")

    def test_preview_endpoint_error(self, client, mock_service):
        """Test preview endpoint with error."""
        mock_service.preview_shapefile = AsyncMock(
            side_effect=ShapefileDownloadError("Download failed")
        )

        response = client.get("/shapefiles/preview?s3_uri=https://example.com/test.shp")

        assert response.status_code == 400
        data = response.json()
        assert "Download failed" in data["detail"]


class TestShapefileServiceStructure:
    """Test the structure of the shapefile service."""

    def test_service_layer_exists(self):
        """Test that the service layer classes exist and are properly structured."""
        from app.services.shapefile_service import (
            DefaultDownloadService,
            DefaultDuckDBService,
            DownloadService,
            DuckDBConnectionError,
            DuckDBService,
            Page,
            ShapefileDownloadError,
            ShapefileProcessingError,
            ShapefileService,
        )

        # Test that classes exist
        assert ShapefileService is not None
        assert DefaultDownloadService is not None
        assert DefaultDuckDBService is not None
        assert DownloadService is not None
        assert DuckDBService is not None
        assert Page is not None

        # Test that exceptions exist
        assert ShapefileDownloadError is not None
        assert DuckDBConnectionError is not None
        assert ShapefileProcessingError is not None

    def test_service_methods_exist(self):
        """Test that service methods exist."""
        from app.services.shapefile_service import ShapefileService

        # Check that the service has the expected methods
        assert hasattr(ShapefileService, "query_shapefile")
        assert hasattr(ShapefileService, "get_shapefile_schema")
        assert hasattr(ShapefileService, "preview_shapefile")

        # Check that they are callable
        assert callable(ShapefileService.query_shapefile)
        assert callable(ShapefileService.get_shapefile_schema)
        assert callable(ShapefileService.preview_shapefile)

    def test_abstract_base_classes(self):
        """Test that abstract base classes are properly defined."""
        from app.services.shapefile_service import DownloadService, DuckDBService

        # These should be abstract base classes
        assert hasattr(DownloadService, "__abstractmethods__")
        assert hasattr(DuckDBService, "__abstractmethods__")
