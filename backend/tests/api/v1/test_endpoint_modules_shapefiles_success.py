from unittest.mock import AsyncMock, patch

import pytest

# Skip all shapefile tests - feature hasn't landed yet
pytestmark = pytest.mark.skip(reason="Shapefile feature hasn't landed yet")


class PageObj:
    def __init__(self, rows=None):
        self._rows = rows or []

    def dict(self):
        return {"total_rows": len(self._rows), "columns": [], "rows": self._rows}


@pytest.mark.asyncio
async def test_query_endpoint_success():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.query_shapefile.return_value = PageObj(rows=[{"id": 1}])
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        resp = await sh.query_endpoint(
            s3_uri="s3://bucket/file.shp", sql="1=1", service=mock_service
        )
        assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_schema_endpoint_success():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.get_shapefile_schema.return_value = [{"name": "id", "type": "INTEGER"}]
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        resp = await sh.schema_endpoint(s3_uri="s3://bucket/file.shp", service=mock_service)
        assert hasattr(resp, "body")


@pytest.mark.asyncio
async def test_preview_endpoint_success():
    from app.api.v1.endpoint_modules import shapefiles as sh

    mock_service = AsyncMock()
    mock_service.preview_shapefile.return_value = PageObj(rows=[{"id": 1}])
    with patch.object(sh, "get_shapefile_service", return_value=mock_service):
        resp = await sh.preview_endpoint(
            s3_uri="s3://bucket/file.shp", limit=5, service=mock_service
        )
        assert hasattr(resp, "body")
