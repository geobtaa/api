import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.utils import create_response
from app.services.shapefile_service import (
    ShapefileService, 
    DefaultDownloadService, 
    DefaultDuckDBService,
    DuckDBConnectionError,
    ShapefileProcessingError,
    ShapefileDownloadError
)

# Load environment variables
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)

# DuckDB configuration
DUCKDB_DATABASE_PATH = os.getenv("DUCKDB_DATABASE_PATH", "data/duckdb/btaa_ogm_api.duckdb")

# Ensure the DuckDB directory exists
os.makedirs(os.path.dirname(DUCKDB_DATABASE_PATH), exist_ok=True)


def get_shapefile_service() -> ShapefileService:
    """Dependency injection for ShapefileService."""
    download_service = DefaultDownloadService()
    duckdb_service = DefaultDuckDBService(DUCKDB_DATABASE_PATH)
    return ShapefileService(download_service, duckdb_service)


@router.get("/shapefiles/query")
async def query_endpoint(
    s3_uri: str = Query(..., description="S3 URI or URL of the shapefile"),
    sql: str = Query(..., description="SQL WHERE clause to filter the data"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: ShapefileService = Depends(get_shapefile_service),
):
    """Query a shapefile using SQL WHERE clauses."""
    try:
        # Use the service to query the shapefile
        page = await service.query_shapefile(s3_uri, sql)
        return create_response(page.dict(), callback)

    except DuckDBConnectionError as e:
        logger.error(f"DuckDB connection error: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except ShapefileDownloadError as e:
        logger.error(f"Shapefile download error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ShapefileProcessingError as e:
        logger.error(f"Shapefile processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error querying shapefile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error querying shapefile: {str(e)}")


@router.get("/shapefiles/schema")
async def schema_endpoint(
    s3_uri: str = Query(..., description="S3 URI or URL of the shapefile"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: ShapefileService = Depends(get_shapefile_service),
):
    """Get the schema of a shapefile."""
    try:
        # Use the service to get the schema
        schema = await service.get_shapefile_schema(s3_uri)
        return create_response(schema, callback)

    except DuckDBConnectionError as e:
        logger.error(f"DuckDB connection error: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except ShapefileDownloadError as e:
        logger.error(f"Shapefile download error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ShapefileProcessingError as e:
        logger.error(f"Shapefile processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting shapefile schema: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting shapefile schema: {str(e)}")


@router.get("/shapefiles/preview")
async def preview_endpoint(
    s3_uri: str = Query(..., description="S3 URI or URL of the shapefile"),
    limit: int = Query(10, description="Maximum number of rows to return", ge=1, le=1000),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: ShapefileService = Depends(get_shapefile_service),
):
    """Preview a shapefile with a limited number of rows."""
    try:
        # Use the service to preview the shapefile
        page = await service.preview_shapefile(s3_uri, limit)
        return create_response(page.dict(), callback)

    except DuckDBConnectionError as e:
        logger.error(f"DuckDB connection error: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except ShapefileDownloadError as e:
        logger.error(f"Shapefile download error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ShapefileProcessingError as e:
        logger.error(f"Shapefile processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error previewing shapefile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error previewing shapefile: {str(e)}")