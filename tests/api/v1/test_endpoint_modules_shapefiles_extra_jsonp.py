from unittest.mock import AsyncMock, patch

import pytest

# Skip all shapefile tests - feature hasn't landed yet
pytestmark = pytest.mark.skip(reason="Shapefile feature hasn't landed yet")


@pytest.mark.asyncio
async def test_query_endpoint_jsonp():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.query_shapefile.return_value = type(
        "P", (), {"dict": lambda self=None: {"total_rows": 0, "columns": [], "rows": []}}
    )()
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        resp = await sh.query_endpoint(
            s3_uri="s3://bucket/file.shp", sql="1=1", callback="cb", service=mock_service
        )
        assert resp is not None


@pytest.mark.asyncio
async def test_schema_endpoint_jsonp():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.get_shapefile_schema.return_value = []
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        resp = await sh.schema_endpoint(
            s3_uri="s3://bucket/file.shp", callback="cb", service=mock_service
        )
        assert resp is not None


@pytest.mark.asyncio
async def test_preview_endpoint_jsonp():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.preview_shapefile.return_value = type(
        "P", (), {"dict": lambda self=None: {"total_rows": 0, "columns": [], "rows": []}}
    )()
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        resp = await sh.preview_endpoint(
            s3_uri="s3://bucket/file.shp", limit=5, callback="cb", service=mock_service
        )
        assert resp is not None
