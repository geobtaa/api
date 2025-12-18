"""
Tests for the shapefile service layer.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.shapefile_service import (
    DefaultDownloadService,
    DefaultDuckDBService,
    DuckDBConnectionError,
    Page,
    ShapefileDownloadError,
    ShapefileProcessingError,
    ShapefileService,
)

# Skip all shapefile tests - feature hasn't landed yet
pytestmark = pytest.mark.skip(reason="Shapefile feature hasn't landed yet")


class TestPage:
    """Test the Page model."""

    def test_page_creation(self):
        """Test creating a Page object."""
        page = Page(
            total_rows=100,
            columns=["id", "name", "geometry"],
            rows=[{"id": 1, "name": "Test", "geometry": "POINT(0 0)"}],
        )
        assert page.total_rows == 100
        assert page.columns == ["id", "name", "geometry"]
        assert len(page.rows) == 1
        assert page.rows[0]["id"] == 1


class TestDefaultDownloadService:
    """Test the default download service."""

    @pytest.mark.asyncio
    async def test_download_shapefile_success(self):
        """Test successful shapefile download."""
        service = DefaultDownloadService()

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = b"fake shapefile content"
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            with patch("tempfile.mkdtemp") as mock_mkdtemp:
                mock_mkdtemp.return_value = "/tmp/test"

                with patch("tempfile.NamedTemporaryFile") as mock_temp:
                    mock_temp_file = Mock()
                    mock_temp_file.name = "/tmp/test/shapefile.shp"
                    mock_temp.return_value = mock_temp_file

                    result = await service.download_shapefile("https://example.com/test.shp")

                    assert result == "/tmp/test/shapefile.shp"
                    mock_get.assert_called_once_with(
                        "https://example.com/test.shp", verify=False, timeout=30
                    )

    @pytest.mark.asyncio
    async def test_download_shapefile_network_error(self):
        """Test download with network error."""
        service = DefaultDownloadService()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(ShapefileDownloadError) as exc_info:
                await service.download_shapefile("https://example.com/test.shp")

            assert "Network error" in str(exc_info.value)


class TestDefaultDuckDBService:
    """Test the default DuckDB service."""

    def test_init(self):
        """Test service initialization."""
        service = DefaultDuckDBService("/tmp/test.duckdb")
        assert service.database_path == "/tmp/test.duckdb"

    def test_get_connection_no_duckdb(self):
        """Test getting connection when DuckDB is not available."""
        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=None)

        with pytest.raises(DuckDBConnectionError) as exc_info:
            service.get_connection()

        assert "DuckDB is not available" in str(exc_info.value)

    def test_get_connection_success(self):
        """Test successful connection creation."""
        mock_con = Mock()
        mock_duckdb = Mock()
        mock_duckdb.connect.return_value = mock_con

        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        result = service.get_connection()

        assert result == mock_con
        mock_duckdb.connect.assert_called_once_with("/tmp/test.duckdb")
        mock_con.execute.assert_any_call("INSTALL spatial")
        mock_con.execute.assert_any_call("LOAD spatial")

    def test_get_connection_error(self):
        """Test connection creation error."""
        mock_duckdb = Mock()
        mock_duckdb.connect.side_effect = Exception("Connection failed")
        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        with pytest.raises(DuckDBConnectionError) as exc_info:
            service.get_connection()

        assert "Failed to create DuckDB connection" in str(exc_info.value)

    def test_ensure_table_exists(self):
        """Test ensuring table that already exists."""
        mock_con = Mock()
        mock_duckdb = Mock()
        mock_duckdb.connect.return_value = mock_con
        # Mock that table exists
        mock_con.execute.return_value.fetchone.return_value = ("shapefile_123",)

        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        result = service.ensure_table(mock_con, "https://example.com/test.shp")

        # Should return the hash-based table name, not the mocked one
        expected_name = f"shapefile_{hash('https://example.com/test.shp') % 1000000}"
        assert result == expected_name
        # Should check if table exists
        mock_con.execute.assert_called_once()

    def test_ensure_table_create_new(self):
        """Test creating a new table."""
        mock_con = Mock()
        mock_duckdb = Mock()
        mock_duckdb.connect.return_value = mock_con
        mock_con.execute.return_value.fetchone.return_value = None

        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        result = service.ensure_table(mock_con, "https://example.com/test.shp")

        # Should create table with hash-based name
        expected_name = f"shapefile_{hash('https://example.com/test.shp') % 1000000}"
        assert result == expected_name
        assert mock_con.execute.call_count == 2  # Check existence + create

    def test_execute_query_success(self):
        """Test successful query execution."""
        mock_con = Mock()
        mock_duckdb = Mock()
        mock_duckdb.connect.return_value = mock_con

        # Mock query result for main query
        mock_result = Mock()
        mock_result.description = [("id",), ("name",), ("geometry",)]
        mock_result.fetchall.return_value = [(1, "Test", "POINT(0 0)")]

        # Mock count query result
        mock_count_result = Mock()
        mock_count_result.fetchone.return_value = (1,)  # Return tuple with count

        # Set up execute to return different results for different queries
        def execute_side_effect(query):
            if "COUNT(*)" in query:
                return mock_count_result
            else:
                return mock_result

        mock_con.execute.side_effect = execute_side_effect

        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        result = service.execute_query(mock_con, "test_table", "id > 0", limit=10, offset=0)

        assert isinstance(result, Page)
        assert result.total_rows == 1  # From count query
        assert result.columns == ["id", "name", "geometry"]
        assert len(result.rows) == 1
        assert result.rows[0]["id"] == 1

    def test_execute_query_error(self):
        """Test query execution error."""
        mock_con = Mock()
        mock_duckdb = Mock()
        mock_duckdb.connect.return_value = mock_con
        mock_con.execute.side_effect = Exception("SQL error")

        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        with pytest.raises(ShapefileProcessingError) as exc_info:
            service.execute_query(mock_con, "test_table", "invalid sql")

        assert "Failed to execute query" in str(exc_info.value)

    def test_get_table_schema_success(self):
        """Test successful schema retrieval."""
        mock_con = Mock()
        mock_duckdb = Mock()
        mock_duckdb.connect.return_value = mock_con

        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ("id", "INTEGER", "NO", "PRI", None, ""),
            ("name", "VARCHAR", "YES", "", None, ""),
        ]
        mock_con.execute.return_value = mock_result

        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        result = service.get_table_schema(mock_con, "test_table")

        assert len(result) == 2
        assert result[0]["column_name"] == "id"
        assert result[0]["column_type"] == "INTEGER"
        assert result[1]["column_name"] == "name"
        assert result[1]["column_type"] == "VARCHAR"

    def test_get_table_schema_error(self):
        """Test schema retrieval error."""
        mock_con = Mock()
        mock_duckdb = Mock()
        mock_duckdb.connect.return_value = mock_con
        mock_con.execute.side_effect = Exception("Schema error")

        service = DefaultDuckDBService("/tmp/test.duckdb", duckdb_module=mock_duckdb)

        with pytest.raises(ShapefileProcessingError) as exc_info:
            service.get_table_schema(mock_con, "nonexistent_table")

        assert "Failed to get table schema" in str(exc_info.value)


class TestShapefileService:
    """Test the main shapefile service."""

    def test_init(self):
        """Test service initialization."""
        download_service = Mock()
        duckdb_service = Mock()

        service = ShapefileService(download_service, duckdb_service)

        assert service.download_service == download_service
        assert service.duckdb_service == duckdb_service

    @pytest.mark.asyncio
    async def test_query_shapefile_success(self):
        """Test successful shapefile query."""
        mock_download_service = Mock()
        mock_duckdb_service = Mock()

        mock_con = Mock()
        mock_duckdb_service.get_connection.return_value = mock_con
        mock_duckdb_service.ensure_table.return_value = "test_table"

        expected_page = Page(
            total_rows=100, columns=["id", "name"], rows=[{"id": 1, "name": "Test"}]
        )
        mock_duckdb_service.execute_query.return_value = expected_page

        service = ShapefileService(mock_download_service, mock_duckdb_service)

        result = await service.query_shapefile("https://example.com/test.shp", "id > 0")

        assert result == expected_page
        mock_duckdb_service.get_connection.assert_called_once()
        mock_duckdb_service.ensure_table.assert_called_once_with(
            mock_con, "https://example.com/test.shp"
        )
        mock_duckdb_service.execute_query.assert_called_once()
        mock_con.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_shapefile_duckdb_error(self):
        """Test query with DuckDB connection error."""
        mock_download_service = Mock()
        mock_duckdb_service = Mock()
        mock_duckdb_service.get_connection.side_effect = DuckDBConnectionError("No DuckDB")

        service = ShapefileService(mock_download_service, mock_duckdb_service)

        with pytest.raises(DuckDBConnectionError):
            await service.query_shapefile("https://example.com/test.shp", "id > 0")

    @pytest.mark.asyncio
    async def test_query_shapefile_processing_error(self):
        """Test query with processing error."""
        mock_download_service = Mock()
        mock_duckdb_service = Mock()

        mock_con = Mock()
        mock_duckdb_service.get_connection.return_value = mock_con
        mock_duckdb_service.ensure_table.return_value = "test_table"
        mock_duckdb_service.execute_query.side_effect = ShapefileProcessingError("SQL error")

        service = ShapefileService(mock_download_service, mock_duckdb_service)

        with pytest.raises(ShapefileProcessingError):
            await service.query_shapefile("https://example.com/test.shp", "invalid sql")

    @pytest.mark.asyncio
    async def test_get_shapefile_schema_success(self):
        """Test successful schema retrieval."""
        mock_download_service = Mock()
        mock_duckdb_service = Mock()

        mock_con = Mock()
        mock_duckdb_service.get_connection.return_value = mock_con
        mock_duckdb_service.ensure_table.return_value = "test_table"
        mock_duckdb_service.get_table_schema.return_value = [
            {"column_name": "id", "column_type": "INTEGER"}
        ]

        service = ShapefileService(mock_download_service, mock_duckdb_service)

        result = await service.get_shapefile_schema("https://example.com/test.shp")

        assert len(result) == 1
        assert result[0]["column_name"] == "id"
        mock_con.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_shapefile_success(self):
        """Test successful shapefile preview."""
        mock_download_service = Mock()
        mock_duckdb_service = Mock()

        expected_page = Page(
            total_rows=100, columns=["id", "name"], rows=[{"id": 1, "name": "Test"}]
        )

        with patch.object(
            ShapefileService, "query_shapefile", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = expected_page

            service = ShapefileService(mock_download_service, mock_duckdb_service)

            result = await service.preview_shapefile("https://example.com/test.shp", limit=10)

            assert result == expected_page
            mock_query.assert_called_once_with(
                "https://example.com/test.shp", "", limit=10, offset=0
            )
