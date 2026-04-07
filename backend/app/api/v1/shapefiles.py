import logging
import os
import tempfile
import zipfile
from typing import Any, Optional
from urllib.parse import urlparse

try:
    import duckdb  # type: ignore

    HAS_DUCKDB = True
except Exception:  # ModuleNotFoundError or other import-time errors
    HAS_DUCKDB = False
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.utils import create_response, sanitize_for_json
from app.security_utils import quote_sql_identifier, safe_extract_zip, stable_hex_digest

# Load environment variables
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)

# DuckDB configuration
DUCKDB_DATABASE_PATH = os.getenv("DUCKDB_DATABASE_PATH", "data/duckdb/btaa_ogm_api.duckdb")

# Ensure the DuckDB directory exists
os.makedirs(os.path.dirname(DUCKDB_DATABASE_PATH), exist_ok=True)


def get_duckdb_connection():
    """Get a DuckDB connection with spatial extension loaded."""
    if not HAS_DUCKDB:
        raise HTTPException(status_code=503, detail="DuckDB is not available on this server")

    con = duckdb.connect(DUCKDB_DATABASE_PATH)
    con.execute("INSTALL spatial")
    con.execute("LOAD spatial")
    return con


class Page(BaseModel):
    total_rows: int
    columns: list[str]
    rows: list[dict[str, Any]]


def _validate_remote_shapefile_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme not in {"http", "https", "s3"}:
        raise HTTPException(
            status_code=400,
            detail="Only http, https, and s3 shapefile URIs are supported",
        )

    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid shapefile URL")

    if parsed.scheme == "s3" and not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid S3 shapefile URI")

    return uri


def _table_name_for_uri(uri: str) -> str:
    return f"shapefile_{stable_hex_digest(uri, digest_size=8)}"


def _quote_table_name(table_name: str) -> str:
    return quote_sql_identifier(table_name, kind="table name")


def _fetch_table_metadata(con: Any, table_name: str):
    return con.execute(
        """
        SELECT column_name AS name, data_type AS type
        FROM information_schema.columns
        WHERE table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).df()


def ensure_table(con: Any, s3_uri: str) -> str:
    """
    Ensure a table exists for the given remote shapefile URI.
    Creates a stable table name based on the URI and loads the shapefile if needed.
    """
    s3_uri = _validate_remote_shapefile_uri(s3_uri)
    table_name = _table_name_for_uri(s3_uri)
    quoted_table_name = _quote_table_name(table_name)

    result = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", [table_name]
    ).fetchone()

    if result is None:
        logger.info(f"Creating table {table_name} for S3 URI: {s3_uri}")

        try:
            if s3_uri.startswith("http"):
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/91.0.4472.124 Safari/537.36"
                    )
                }

                with requests.get(s3_uri, stream=True, headers=headers, timeout=30) as response:
                    response.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
                        for chunk in response.iter_content(chunk_size=8192):
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name

                try:
                    if zipfile.is_zipfile(temp_file_path):
                        logger.info("File is a ZIP archive, extracting...")

                        with tempfile.TemporaryDirectory() as extract_dir:
                            with zipfile.ZipFile(temp_file_path, "r") as zip_ref:
                                safe_extract_zip(zip_ref, extract_dir)

                            shp_files: list[str] = []
                            for root, _dirs, files in os.walk(extract_dir):
                                for file in files:
                                    if file.lower().endswith(".shp"):
                                        shp_files.append(os.path.join(root, file))

                            if not shp_files:
                                raise HTTPException(
                                    status_code=400,
                                    detail="No shapefile (.shp) found in ZIP archive",
                                )

                            shapefile_path = shp_files[0]
                            logger.info(f"Found shapefile: {shapefile_path}")
                            con.execute(
                                f"CREATE TABLE {quoted_table_name} AS SELECT * FROM st_read(?)",
                                [shapefile_path],
                            )
                    else:
                        con.execute(
                            f"CREATE TABLE {quoted_table_name} AS SELECT * FROM st_read(?)",
                            [temp_file_path],
                        )

                    logger.info(
                        f"Successfully loaded shapefile from {s3_uri} into table {table_name}"
                    )
                finally:
                    os.unlink(temp_file_path)

            elif s3_uri.startswith("s3://"):
                con.execute(
                    f"CREATE TABLE {quoted_table_name} AS SELECT * FROM st_read(?)", [s3_uri]
                )
            else:
                raise HTTPException(status_code=400, detail="Unsupported shapefile URI")

        except Exception as e:
            logger.error(f"Error loading shapefile from {s3_uri}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error loading shapefile: {str(e)}") from e

    return table_name


@router.get("/shapefiles")
async def shapefile_table(
    s3_uri: str = Query(..., description="Full S3 URI to *.shp or *.zip"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, le=1000, description="Items per page"),
    sort: Optional[str] = Query(None, description="Column to sort by"),
    dir: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction"),
    q: Optional[str] = Query(None, description="Free-text search"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get shapefile data from S3, paginated and searchable."""
    try:
        s3_uri = _validate_remote_shapefile_uri(s3_uri)
        if not HAS_DUCKDB:
            raise HTTPException(status_code=503, detail="DuckDB is not available on this server")
        con = get_duckdb_connection()

        table_name = ensure_table(con, s3_uri)
        quoted_table_name = _quote_table_name(table_name)
        meta = _fetch_table_metadata(con, table_name)
        cols = meta["name"].tolist()

        geom_cols = []
        text_cols = []

        for _, row in meta.iterrows():
            col_name = row["name"]
            col_type = row["type"]

            if (
                col_name.lower() in ["geometry", "geom", "shape", "wkb_geometry"]
                or col_type.upper() in ["BLOB", "STRUCT", "VARCHAR"]
                and "geometry" in col_name.lower()
            ):
                geom_cols.append(col_name)
            else:
                text_cols.append(col_name)

        if sort is None:
            sort = text_cols[0] if text_cols else cols[0]

        if sort not in cols:
            raise HTTPException(status_code=400, detail=f"Unknown sort column: {sort}")

        where = "TRUE"
        query_params: list[Any] = []
        if q:
            ors = [
                f"{quote_sql_identifier(column_name, kind='column name')}::TEXT ILIKE ?"
                for column_name in text_cols
            ]
            where = " OR ".join(ors) if ors else "TRUE"
            query_params = [f"%{q}%"] * len(text_cols)

        limit = size
        offset = (page - 1) * size

        total = con.execute(
            f"SELECT COUNT(*) FROM {quoted_table_name} WHERE {where}", query_params
        ).fetchone()[0]

        sql = f"""
            SELECT *
            FROM {quoted_table_name}
            WHERE {where}
            ORDER BY {quote_sql_identifier(sort, kind="column name")} {dir.upper()}
            LIMIT ? OFFSET ?
        """

        logger.info(f"Executing SQL: {sql}")
        df = con.execute(sql, [*query_params, limit, offset]).fetch_df()

        if geom_cols:
            df = df.drop(columns=geom_cols)

        rows = df.astype(object).where(pd.notnull(df), None).to_dict(orient="records")

        response_data = {
            "total_rows": total,
            "columns": [c for c in cols if c not in geom_cols],
            "rows": rows,
            "page": page,
            "size": size,
            "total_pages": (total + size - 1) // size,
            "s3_uri": s3_uri,
            "table_name": table_name,
        }

        return create_response(sanitize_for_json(response_data), callback)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing shapefile request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e
    finally:
        if "con" in locals():
            con.close()


@router.get("/shapefiles/{table_name}/info")
async def shapefile_info(
    table_name: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get metadata about a specific shapefile table."""
    try:
        if not HAS_DUCKDB:
            raise HTTPException(status_code=503, detail="DuckDB is not available on this server")
        con = get_duckdb_connection()
        quoted_table_name = _quote_table_name(table_name)

        result = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", [table_name]
        ).fetchone()
        if result is None:
            raise HTTPException(status_code=404, detail=f"Table {table_name} not found")

        meta = _fetch_table_metadata(con, table_name)
        cols = meta["name"].tolist()
        count = con.execute(f"SELECT COUNT(*) FROM {quoted_table_name}").fetchone()[0]
        sample = con.execute(f"SELECT * FROM {quoted_table_name} LIMIT 5").fetch_df()

        response_data = {
            "table_name": table_name,
            "columns": cols,
            "total_rows": count,
            "sample_data": sample.to_dict(orient="records"),
        }

        return create_response(sanitize_for_json(response_data), callback)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting shapefile info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e
    finally:
        if "con" in locals():
            con.close()


@router.get("/shapefiles/tables")
async def list_shapefile_tables(
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """List all available shapefile tables."""
    try:
        if not HAS_DUCKDB:
            raise HTTPException(status_code=503, detail="DuckDB is not available on this server")
        con = get_duckdb_connection()

        tables = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'shapefile_%'"
        ).fetchall()

        table_info = []
        for (table_name,) in tables:
            count = con.execute(f"SELECT COUNT(*) FROM {_quote_table_name(table_name)}").fetchone()[
                0
            ]
            table_info.append({"table_name": table_name, "row_count": count})

        response_data = {"tables": table_info, "total_tables": len(table_info)}
        return create_response(sanitize_for_json(response_data), callback)

    except Exception as e:
        logger.error(f"Error listing shapefile tables: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e
    finally:
        if "con" in locals():
            con.close()
