"""
Service layer for shapefile operations.
Provides abstraction for downloading, processing, and querying shapefiles.
"""

import logging
import tempfile
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

import requests
import urllib3
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Suppress SSL warnings when verification is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class DuckDBConnection(Protocol):
    """Protocol for DuckDB connection interface."""

    def execute(self, query: str) -> Any:
        """Execute a SQL query."""
        ...

    def close(self) -> None:
        """Close the connection."""
        ...


class DuckDBModule(Protocol):
    """Protocol for DuckDB module interface."""

    def connect(self, database_path: str) -> DuckDBConnection:
        """Connect to a DuckDB database."""
        ...


def get_duckdb_module() -> Optional[DuckDBModule]:
    """Get DuckDB module if available."""
    try:
        import duckdb  # type: ignore

        return duckdb
    except ImportError:
        return None


class Page(BaseModel):
    """Model for paginated query results."""

    total_rows: int
    columns: list[str]
    rows: list[dict[str, Any]]


class ShapefileDownloadError(Exception):
    """Raised when shapefile download fails."""

    pass


class DuckDBConnectionError(Exception):
    """Raised when DuckDB connection fails."""

    pass


class ShapefileProcessingError(Exception):
    """Raised when shapefile processing fails."""

    pass


class DownloadService(ABC):
    """Abstract base class for shapefile download services."""

    @abstractmethod
    async def download_shapefile(self, url: str) -> str:
        """Download shapefile and return local file path."""
        pass


class DuckDBService(ABC):
    """Abstract base class for DuckDB operations."""

    @abstractmethod
    def get_connection(self):
        """Get a DuckDB connection."""
        pass

    @abstractmethod
    def ensure_table(self, con: Any, s3_uri: str) -> str:
        """Ensure a table exists for the given S3 URI."""
        pass

    @abstractmethod
    def execute_query(
        self, con: Any, table_name: str, sql: str, limit: Optional[int] = None, offset: int = 0
    ) -> Page:
        """Execute a query on the specified table."""
        pass

    @abstractmethod
    def get_table_schema(self, con: Any, table_name: str) -> list[dict[str, Any]]:
        """Get schema information for a table."""
        pass


class DefaultDownloadService(DownloadService):
    """Default implementation of shapefile download service."""

    async def download_shapefile(self, url: str) -> str:
        """Download shapefile and return local file path."""
        try:
            # Create temporary directory for downloads
            temp_dir = tempfile.mkdtemp()

            # Download the shapefile
            response = requests.get(url, verify=False, timeout=30)
            response.raise_for_status()

            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".shp", dir=temp_dir, delete=False)
            temp_file.write(response.content)
            temp_file.close()

            logger.info(f"Downloaded shapefile to: {temp_file.name}")
            return temp_file.name

        except requests.RequestException as e:
            raise ShapefileDownloadError(
                f"Failed to download shapefile from {url}: {str(e)}"
            ) from e
        except Exception as e:
            raise ShapefileDownloadError(f"Unexpected error downloading shapefile: {str(e)}") from e


class DefaultDuckDBService(DuckDBService):
    """Default implementation of DuckDB service."""

    def __init__(self, database_path: str, duckdb_module: Optional[DuckDBModule] = None):
        self.database_path = database_path
        self.duckdb_module = duckdb_module or get_duckdb_module()

    def get_connection(self):
        """Get a DuckDB connection with spatial extension loaded."""
        if not self.duckdb_module:
            raise DuckDBConnectionError("DuckDB is not available on this server")

        try:
            con = self.duckdb_module.connect(self.database_path)
            # Load the spatial extension for shapefile support
            con.execute("INSTALL spatial")
            con.execute("LOAD spatial")
            return con
        except Exception as e:
            raise DuckDBConnectionError(f"Failed to create DuckDB connection: {str(e)}") from e

    def ensure_table(self, con: Any, s3_uri: str) -> str:
        """
        Ensure a table exists for the given S3 URI.
        Creates a table name based on the URI and loads the shapefile if needed.
        """
        # Create a table name from the S3 URI
        table_name = f"shapefile_{hash(s3_uri) % 1000000}"

        # Check if table exists
        result = con.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        ).fetchone()

        if result is None:
            # Table doesn't exist, create it
            # For now, we'll create an empty table
            # In a real implementation, this would load the shapefile
            con.execute(f"""
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY,
                    geometry GEOMETRY,
                    properties JSON
                )
            """)
            logger.info(f"Created table: {table_name}")
        else:
            logger.info(f"Table already exists: {table_name}")

        return table_name

    def execute_query(
        self, con: Any, table_name: str, sql: str, limit: Optional[int] = None, offset: int = 0
    ) -> Page:
        """Execute a query on the specified table."""
        try:
            # Build the full query
            full_query = f"SELECT * FROM {table_name}"
            if sql.strip():
                full_query += f" WHERE {sql}"

            # Add pagination
            if limit:
                full_query += f" LIMIT {limit} OFFSET {offset}"

            # Execute query
            result = con.execute(full_query)

            # Get column names
            columns = [desc[0] for desc in result.description]

            # Get rows
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

            # Get total count
            count_query = f"SELECT COUNT(*) FROM {table_name}"
            if sql.strip():
                count_query += f" WHERE {sql}"

            total_rows = con.execute(count_query).fetchone()[0]

            return Page(total_rows=total_rows, columns=columns, rows=rows)

        except Exception as e:
            raise ShapefileProcessingError(f"Failed to execute query: {str(e)}") from e

    def get_table_schema(self, con: Any, table_name: str) -> list[dict[str, Any]]:
        """Get schema information for a table."""
        try:
            result = con.execute(f"DESCRIBE {table_name}")
            schema = []
            for row in result.fetchall():
                schema.append(
                    {
                        "column_name": row[0],
                        "column_type": row[1],
                        "null": row[2],
                        "key": row[3],
                        "default": row[4],
                        "extra": row[5],
                    }
                )
            return schema
        except Exception as e:
            raise ShapefileProcessingError(f"Failed to get table schema: {str(e)}") from e


class ShapefileService:
    """Main service for shapefile operations."""

    def __init__(self, download_service: DownloadService, duckdb_service: DuckDBService):
        self.download_service = download_service
        self.duckdb_service = duckdb_service

    async def query_shapefile(
        self, s3_uri: str, sql: str, limit: Optional[int] = None, offset: int = 0
    ) -> Page:
        """Query a shapefile using SQL."""
        try:
            # Get DuckDB connection
            con = self.duckdb_service.get_connection()

            # Ensure table exists
            table_name = self.duckdb_service.ensure_table(con, s3_uri)

            # Execute query
            result = self.duckdb_service.execute_query(con, table_name, sql, limit, offset)

            # Close connection
            con.close()

            return result

        except (DuckDBConnectionError, ShapefileProcessingError) as e:
            raise e
        except Exception as e:
            raise ShapefileProcessingError(f"Unexpected error querying shapefile: {str(e)}") from e

    async def get_shapefile_schema(self, s3_uri: str) -> list[dict[str, Any]]:
        """Get schema information for a shapefile."""
        try:
            # Get DuckDB connection
            con = self.duckdb_service.get_connection()

            # Ensure table exists
            table_name = self.duckdb_service.ensure_table(con, s3_uri)

            # Get schema
            schema = self.duckdb_service.get_table_schema(con, table_name)

            # Close connection
            con.close()

            return schema

        except (DuckDBConnectionError, ShapefileProcessingError) as e:
            raise e
        except Exception as e:
            raise ShapefileProcessingError(
                f"Unexpected error getting shapefile schema: {str(e)}"
            ) from e

    async def preview_shapefile(self, s3_uri: str, limit: int = 10) -> Page:
        """Preview a shapefile with a limited number of rows."""
        return await self.query_shapefile(s3_uri, "", limit=limit, offset=0)
