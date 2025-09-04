import logging
import os
import tempfile
from typing import Any, Optional

try:
    import duckdb  # type: ignore

    HAS_DUCKDB = True
except Exception:  # ModuleNotFoundError or other import-time errors
    HAS_DUCKDB = False
import requests
import urllib3
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.utils import create_response

# Load environment variables
load_dotenv()

# Suppress SSL warnings when verification is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()
logger = logging.getLogger(__name__)

# DuckDB configuration
DUCKDB_DATABASE_PATH = os.getenv("DUCKDB_DATABASE_PATH", "data/duckdb/btaa_ogm_api.duckdb")

# Ensure the DuckDB directory exists
os.makedirs(os.path.dirname(DUCKDB_DATABASE_PATH), exist_ok=True)


# Initialize DuckDB connection
def get_duckdb_connection():
    """Get a DuckDB connection with spatial extension loaded."""
    if not HAS_DUCKDB:
        raise HTTPException(status_code=503, detail="DuckDB is not available on this server")

    con = duckdb.connect(DUCKDB_DATABASE_PATH)
    # Load the spatial extension for shapefile support
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    return con


class Page(BaseModel):
    total_rows: int
    columns: list[str]
    rows: list[dict[str, Any]]


def ensure_table(con: Any, s3_uri: str) -> str:
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
        logger.info(f"Creating table {table_name} for S3 URI: {s3_uri}")

        # Load the shapefile into DuckDB
        try:
            # For URLs, download the file first
            if s3_uri.startswith("http"):
                logger.info(f"Downloading file from URL: {s3_uri}")

                # Download the file with SSL verification disabled for problematic servers
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/91.0.4472.124 Safari/537.36"
                    )
                }

                try:
                    # First try with SSL verification
                    response = requests.get(s3_uri, stream=True, headers=headers, timeout=30)
                    response.raise_for_status()
                except requests.exceptions.SSLError:
                    logger.warning(
                        f"SSL verification failed for {s3_uri}, retrying without verification"
                    )
                    # Retry without SSL verification
                    response = requests.get(
                        s3_uri, stream=True, headers=headers, verify=False, timeout=30
                    )
                    response.raise_for_status()

                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        tmp_file.write(chunk)
                    tmp_file_path = tmp_file.name

                try:
                    # Load the shapefile
                    con.execute(f"COPY '{tmp_file_path}' TO '{table_name}' (FORMAT SHAPEFILE)")
                    logger.info(f"Successfully loaded shapefile into table {table_name}")
                finally:
                    # Clean up temporary file
                    os.unlink(tmp_file_path)

            else:
                # For local files, load directly
                con.execute(f"COPY '{s3_uri}' TO '{table_name}' (FORMAT SHAPEFILE)")
                logger.info(f"Successfully loaded local shapefile into table {table_name}")

        except Exception as e:
            logger.error(f"Failed to load shapefile {s3_uri}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to load shapefile: {str(e)}"
            ) from e

    return table_name


@router.get("/shapefiles/query")
async def query_shapefile(
    s3_uri: str = Query(..., description="S3 URI or URL to the shapefile"),
    query: str = Query(..., description="SQL query to execute on the shapefile"),
    limit: int = Query(100, description="Maximum number of rows to return", ge=1, le=1000),
    offset: int = Query(0, description="Number of rows to skip", ge=0),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Query a shapefile using SQL."""
    try:
        con = get_duckdb_connection()

        try:
            # Ensure the table exists
            table_name = ensure_table(con, s3_uri)

            # Execute the query with limit and offset
            full_query = f"{query} LIMIT {limit} OFFSET {offset}"
            logger.info(f"Executing query: {full_query}")

            result = con.execute(full_query)
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description]

            # Convert rows to list of dicts
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Handle special types
                    if hasattr(value, "__dict__"):
                        value = str(value)
                    elif isinstance(value, (bytes, bytearray)):
                        value = value.hex()
                    row_dict[col] = value
                data.append(row_dict)

            # Get total count for pagination
            count_query = f"SELECT COUNT(*) FROM ({query})"
            total_rows = con.execute(count_query).fetchone()[0]

            response_data = {
                "data": {
                    "type": "shapefile_query",
                    "attributes": {
                        "s3_uri": s3_uri,
                        "table_name": table_name,
                        "query": query,
                        "page": Page(
                            total_rows=total_rows,
                            columns=columns,
                            rows=data,
                        ),
                    },
                }
            }

            return create_response(response_data, callback)

        finally:
            con.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying shapefile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query shapefile: {str(e)}") from e


@router.get("/shapefiles/schema")
async def get_shapefile_schema(
    s3_uri: str = Query(..., description="S3 URI or URL to the shapefile"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get the schema of a shapefile."""
    try:
        con = get_duckdb_connection()

        try:
            # Ensure the table exists
            table_name = ensure_table(con, s3_uri)

            # Get table schema
            schema_query = f"DESCRIBE {table_name}"
            result = con.execute(schema_query)
            schema_rows = result.fetchall()

            # Convert schema to list of dicts
            schema = []
            for row in schema_rows:
                schema.append(
                    {
                        "column": row[0],
                        "type": row[1],
                        "null": row[2],
                        "key": row[3],
                        "default": row[4],
                        "extra": row[5],
                    }
                )

            # Get table info
            info_query = f"SELECT COUNT(*) FROM {table_name}"
            total_rows = con.execute(info_query).fetchone()[0]

            response_data = {
                "data": {
                    "type": "shapefile_schema",
                    "attributes": {
                        "s3_uri": s3_uri,
                        "table_name": table_name,
                        "total_rows": total_rows,
                        "schema": schema,
                    },
                }
            }

            return create_response(response_data, callback)

        finally:
            con.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting shapefile schema: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get shapefile schema: {str(e)}"
        ) from e


@router.get("/shapefiles/preview")
async def preview_shapefile(
    s3_uri: str = Query(..., description="S3 URI or URL to the shapefile"),
    limit: int = Query(10, description="Maximum number of rows to return", ge=1, le=100),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get a preview of a shapefile (first few rows)."""
    try:
        con = get_duckdb_connection()

        try:
            # Ensure the table exists
            table_name = ensure_table(con, s3_uri)

            # Get preview data
            preview_query = f"SELECT * FROM {table_name} LIMIT {limit}"
            result = con.execute(preview_query)
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description]

            # Convert rows to list of dicts
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Handle special types
                    if hasattr(value, "__dict__"):
                        value = str(value)
                    elif isinstance(value, (bytes, bytearray)):
                        value = value.hex()
                    row_dict[col] = value
                data.append(row_dict)

            # Get total count
            count_query = f"SELECT COUNT(*) FROM {table_name}"
            total_rows = con.execute(count_query).fetchone()[0]

            response_data = {
                "data": {
                    "type": "shapefile_preview",
                    "attributes": {
                        "s3_uri": s3_uri,
                        "table_name": table_name,
                        "total_rows": total_rows,
                        "preview_rows": limit,
                        "columns": columns,
                        "rows": data,
                    },
                }
            }

            return create_response(response_data, callback)

        finally:
            con.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing shapefile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to preview shapefile: {str(e)}") from e
