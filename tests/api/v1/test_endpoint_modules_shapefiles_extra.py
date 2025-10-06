import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_query_endpoint_duckdb_error():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.query_shapefile.side_effect = sh.DuckDBConnectionError("no duckdb")
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        with pytest.raises(HTTPException) as exc:
            await sh.query_endpoint(s3_uri="s3://bucket/file.shp", sql="id > 0", service=mock_service)
        assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_schema_endpoint_processing_error():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.get_shapefile_schema.side_effect = sh.ShapefileProcessingError("bad")
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        with pytest.raises(HTTPException) as exc:
            await sh.schema_endpoint(s3_uri="s3://bucket/file.shp", service=mock_service)
        assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_preview_endpoint_download_error():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.preview_shapefile.side_effect = sh.ShapefileDownloadError("dl")
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        with pytest.raises(HTTPException) as exc:
            await sh.preview_endpoint(s3_uri="s3://bucket/file.shp", limit=5, service=mock_service)
        assert exc.value.status_code == 400

