"""Tests for /resources/{id}/metadata/display endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.resources import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

RESOURCE_ID = "test-resource-123"
ISO_URL = "http://example.com/iso.xml"
HTML_URL = "http://example.com/metadata.html"

SAMPLE_ISO_XML = """<?xml version="1.0"?>
<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd"
    xmlns:gco="http://www.isotc211.org/2005/gco">
  <gmd:identificationInfo>
    <gmd:MD_DataIdentification>
      <gmd:citation><gmd:CI_Citation>
        <gmd:title><gco:CharacterString>Test</gco:CharacterString></gmd:title>
      </gmd:CI_Citation></gmd:citation>
    </gmd:MD_DataIdentification>
  </gmd:identificationInfo>
</gmd:MD_Metadata>
"""

SAMPLE_HTML = "<!DOCTYPE html><html><head><title>Meta</title></head><body>Metadata</body></html>"


class TestMetadataDisplayEndpoint:
    """Test metadata display endpoint."""

    def test_missing_format_returns_422(self):
        """Missing format query param returns 422."""
        response = client.get(f"/resources/{RESOURCE_ID}/metadata/display")
        assert response.status_code == 422

    def test_invalid_format_returns_400(self):
        """Invalid format returns 400."""
        response = client.get(f"/resources/{RESOURCE_ID}/metadata/display?format=invalid")
        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]

    def test_resource_not_found_returns_404(self):
        """Unknown resource returns 404 when no row in DB."""
        with patch(
            "app.api.v1.endpoint_modules.resources.metadata.get_async_session"
        ) as mock_get_session:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            response = client.get("/resources/nonexistent-uuid-12345/metadata/display?format=iso")
            assert response.status_code == 404

    def test_iso_format_transform_success(self):
        """ISO format fetches, transforms, and returns HTML when resource exists."""
        mock_row = MagicMock()
        mock_row._mapping = {
            "id": RESOURCE_ID,
            "dct_title_s": "Test",
            "dct_references_s": None,
        }
        mock_ctx = MagicMock()
        mock_ctx.by_uri = {
            "http://www.isotc211.org/schemas/2005/gmd/": [
                MagicMock(url=ISO_URL),
            ],
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=SAMPLE_ISO_XML)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        async def mock_session_context():
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = mock_row
            mock_conn.execute = AsyncMock(return_value=mock_result)
            yield mock_conn

        with (
            patch(
                "app.api.v1.endpoint_modules.resources.metadata.get_async_session"
            ) as mock_get_session,
            patch(
                "app.api.v1.endpoint_modules.resources.metadata.fetch_distribution_context",
                new_callable=AsyncMock,
            ) as mock_fetch_dist,
            patch("aiohttp.ClientSession") as mock_aio_cls,
        ):
            mock_session = MagicMock()
            mock_session.execute = AsyncMock(
                return_value=MagicMock(fetchone=MagicMock(return_value=mock_row))
            )
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            mock_fetch_dist.return_value = mock_ctx

            mock_aio_session = MagicMock()
            mock_aio_session.get = MagicMock(return_value=mock_resp)
            mock_aio_session.__aenter__ = AsyncMock(return_value=mock_aio_session)
            mock_aio_session.__aexit__ = AsyncMock(return_value=None)
            mock_aio_cls.return_value = mock_aio_session

            response = client.get(f"/resources/{RESOURCE_ID}/metadata/display?format=iso")

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert "<html" in response.text.lower()
            assert "Test" in response.text
