import json

import pytest

import app.services.download_service as download_module
from app.services.download_service import (
    DownloadOption,
    DownloadService,
    IIIFDownloadService,
)


@pytest.fixture
def mock_item_with_iiif():
    """Return a mock item with IIIF references."""
    return {
        "id": "test-item-iiif",
        "dct_title_s": "Test IIIF Item",
        "dct_format_s": "JPEG",
        "dct_references_s": json.dumps(
            {
                "http://iiif.io/api/image": "https://example.com/iiif/image/info.json",
                "http://iiif.io/api/presentation#manifest": "https://example.com/iiif/manifest",
            }
        ),
    }


@pytest.fixture
def mock_item_with_direct_download():
    """Return a mock item with direct download URL."""
    return {
        "id": "test-item-download",
        "dct_title_s": "Test Download Item",
        "dct_format_s": "PDF",
        "dct_references_s": json.dumps(
            {
                "http://schema.org/downloadUrl": "https://example.com/download/document.pdf",
            }
        ),
    }


@pytest.fixture
def mock_item_with_download_info_list():
    """Return a mock item with list of download info objects."""
    return {
        "id": "test-item-download-list",
        "dct_title_s": "Test Multiple Downloads Item",
        "dct_format_s": "Mixed",
        "dct_references_s": json.dumps(
            {
                "http://schema.org/downloadUrl": [
                    {"label": "PDF Version", "url": "https://example.com/download/document.pdf"},
                    {"label": "ZIP Archive", "url": "https://example.com/download/data.zip"},
                ],
            }
        ),
    }


@pytest.fixture
def mock_item_with_download_info_dict():
    """Return a mock item with download info as dictionary."""
    return {
        "id": "test-item-download-dict",
        "dct_title_s": "Test Single Download Info Item",
        "dct_format_s": "TIFF",
        "dct_references_s": json.dumps(
            {
                "http://schema.org/downloadUrl": {
                    "label": "High Resolution Image",
                    "url": "https://example.com/download/image.tiff",
                },
            }
        ),
    }


@pytest.fixture
def mock_item_with_service():
    """Return a mock item with WMS/WFS services."""
    return {
        "id": "test-item-service",
        "dct_title_s": "Test Service Item",
        "gbl_wxsidentifier_s": "test_layer",
        "dct_references_s": json.dumps(
            {
                "http://www.opengis.net/def/serviceType/ogc/wms": "https://example.com/geoserver/wms",
                "http://www.opengis.net/def/serviceType/ogc/wfs": "https://example.com/geoserver/wfs",
            }
        ),
    }


class TestIIIFDownloadService:
    """Test cases for IIIFDownloadService."""

    def test_init(self):
        """Test initialization with references."""
        references = {
            "http://iiif.io/api/image": "https://example.com/iiif/image/info.json",
            "http://iiif.io/api/presentation#manifest": "https://example.com/iiif/manifest",
        }
        service = IIIFDownloadService(references)

        assert service.image_api_endpoint == "https://example.com/iiif/image/info.json"
        assert service.manifest_url == "https://example.com/iiif/manifest"

    def test_get_download_options(self):
        """Test generating download options for IIIF images."""
        references = {"http://iiif.io/api/image": "https://example.com/iiif/image/info.json"}
        service = IIIFDownloadService(references)
        options = service.get_download_options()

        # Should have options for thumb, small, medium, large, and full
        assert len(options) == 5

        # Verify thumb option
        thumb = next(opt for opt in options if opt["label"] == "Thumb Image")
        assert thumb["url"] == "https://example.com/iiif/image/full/150,150/0/default.jpg"
        assert thumb["type"] == "image/jpeg"

        # Verify full option
        full = next(opt for opt in options if opt["label"] == "Full Resolution Image")
        assert full["url"] == "https://example.com/iiif/image/full/full/0/default.jpg"
        assert full["type"] == "image/jpeg"

    def test_no_image_endpoint(self):
        """Test behavior when no image endpoint is available."""
        service = IIIFDownloadService({})
        options = service.get_download_options()
        assert options == []


class TestDownloadService:
    """Test cases for DownloadService."""

    def test_parse_references(self, mock_item_with_iiif):
        """Test parsing references from item."""
        service = DownloadService(mock_item_with_iiif)
        refs = service._parse_references()

        assert "http://iiif.io/api/image" in refs
        assert refs["http://iiif.io/api/image"] == "https://example.com/iiif/image/info.json"

    def test_parse_references_with_invalid_json(self):
        """Test parsing references with invalid JSON."""
        doc = {"dct_references_s": "{invalid json}"}
        service = DownloadService(doc)
        refs = service._parse_references()

        assert refs == {}

    def test_get_direct_downloads_url_string(self, mock_item_with_direct_download):
        """Test getting direct download URL as string."""
        service = DownloadService(mock_item_with_direct_download)
        downloads = service._get_direct_downloads()

        assert len(downloads) == 1
        assert downloads[0]["label"] == "Download PDF"
        assert downloads[0]["url"] == "https://example.com/download/document.pdf"
        assert downloads[0]["format"] == "pdf"

    def test_get_direct_downloads_list(self, mock_item_with_download_info_list):
        """Test getting direct downloads as list."""
        service = DownloadService(mock_item_with_download_info_list)
        downloads = service._get_direct_downloads()

        assert len(downloads) == 2
        assert downloads[0]["label"] == "PDF Version"
        assert downloads[0]["format"] == "pdf"
        assert downloads[1]["label"] == "ZIP Archive"
        assert downloads[1]["format"] == "zip"

    def test_get_direct_downloads_dict(self, mock_item_with_download_info_dict):
        """Test getting direct downloads as dict."""
        service = DownloadService(mock_item_with_download_info_dict)
        downloads = service._get_direct_downloads()

        assert len(downloads) == 1
        assert downloads[0]["label"] == "High Resolution Image"
        assert downloads[0]["format"] == "tiff"

    def test_guess_format(self):
        """Test guessing format from URL."""
        service = DownloadService({})

        assert service._guess_format("file.pdf") == "pdf"
        assert service._guess_format("data.zip") == "zip"
        assert service._guess_format("image.tiff") == "tiff"
        assert service._guess_format("data.json") == "json"
        assert service._guess_format("unknown.xyz") == "unknown"

    def test_get_service_url(self, mock_item_with_service):
        """Test getting service URL by type."""
        service = DownloadService(mock_item_with_service)

        wms_url = service._get_service_url("wms")
        assert wms_url == "https://example.com/geoserver/wms"

        wfs_url = service._get_service_url("wfs")
        assert wfs_url == "https://example.com/geoserver/wfs"

        # Test with unsupported service type
        unknown_url = service._get_service_url("unknown")
        assert unknown_url is None

    def test_build_download_url(self, mock_item_with_service):
        """Test building download URL with parameters."""
        service = DownloadService(mock_item_with_service)

        # Test WMS GetMap option
        wms_option = DownloadOption(
            label="WMS Preview",
            type="image",
            extension="png",
            service_type="wms",
            content_type="image/png",
            request_params={
                "SERVICE": "WMS",
                "VERSION": "1.1.1",
                "REQUEST": "GetMap",
                "LAYERS": "test_layer",
                "WIDTH": 800,
                "HEIGHT": 600,
                "FORMAT": "image/png",
                "SRS": "EPSG:4326",
                "BBOX": "-180,-90,180,90",
            },
            reflect=False,
        )

        url = service._build_download_url(wms_option)
        assert "https://example.com/geoserver/wms" in url
        assert "SERVICE=WMS" in url
        assert "REQUEST=GetMap" in url
        assert "LAYERS=test_layer" in url

        # Test with reflect option
        reflect_option = DownloadOption(
            label="WFS GeoJSON",
            type="data",
            extension="json",
            service_type="wfs",
            content_type="application/json",
            request_params={
                "SERVICE": "WFS",
                "VERSION": "2.0.0",
                "REQUEST": "GetFeature",
                "TYPENAME": "test_layer",
                "OUTPUTFORMAT": "application/json",
            },
            reflect=True,
        )

        url = service._build_download_url(reflect_option)
        assert "https://example.com/geoserver/wfs/reflect" in url
        assert "SERVICE=WFS" in url
        assert "REQUEST=GetFeature" in url

    def test_get_download_options_iiif(self, mock_item_with_iiif):
        """Test getting download options for IIIF item."""
        service = DownloadService(mock_item_with_iiif)
        options = service.get_download_options()

        # Should have options from IIIF service
        assert len(options) == 5

        # Verify thumb and full options exist
        labels = [opt["label"] for opt in options]
        assert "Thumb Image" in labels
        assert "Full Resolution Image" in labels

    def test_get_download_options_direct(self, mock_item_with_direct_download):
        """Test getting download options for direct download item."""
        service = DownloadService(mock_item_with_direct_download)
        options = service.get_download_options()

        assert len(options) == 1
        assert options[0]["label"] == "Download PDF"
        assert options[0]["url"] == "https://example.com/download/document.pdf"
        assert options[0]["type"] == "pdf"

    def test_build_download_url_no_service_url(self):
        """Test building download URL when service URL is not available."""
        service = DownloadService({"id": "test"})

        # Create a download option with a service type that won't have a URL
        option = DownloadOption(
            label="Test Download",
            type="test",
            extension="test",
            service_type="nonexistent_service",
            content_type="application/test",
            request_params={"param": "value"},
        )

        # This should return None because _get_service_url returns None for nonexistent_service
        result = service._build_download_url(option)
        assert result is None

    def test_get_generated_download_options(self):
        """Generated links are added when WFS/WMS and layer metadata are present."""
        service = DownloadService(
            {
                "id": "stanford-bs024ty5255",
                "gbl_wxsIdentifier_s": "druid:bs024ty5255",
                "dcat_bbox": "ENVELOPE(-123.0,-122.0,38.0,37.0)",
                "dct_references_s": json.dumps(
                    {
                        "http://www.opengis.net/def/serviceType/ogc/wfs": (
                            "https://example.com/geoserver/wfs"
                        ),
                        "http://www.opengis.net/def/serviceType/ogc/wms": (
                            "https://example.com/geoserver/wms"
                        ),
                    }
                ),
            }
        )

        options = service.get_generated_download_options()
        labels = {item["label"] for item in options}

        assert "EPSG:4326 Shapefile" in labels
        assert "KMZ" in labels
        assert "GeoJSON" in labels
        assert "CSV" in labels
        assert "GeoTIFF" in labels
        assert all(item.get("generated") is True for item in options)

    @pytest.mark.asyncio
    async def test_ensure_generated_download_creates_file(self, monkeypatch, tmp_path):
        """Generated downloads are fetched, validated, and written to cache path."""

        class FakeResponse:
            status_code = 200
            headers = {"Content-Type": "application/zip"}
            content = b"zip-bytes"

            def raise_for_status(self):
                return None

        def fake_get(url, params=None, timeout=30):
            assert url == "https://example.com/geoserver/wfs"
            assert params is not None
            assert params["typeName"] == "druid:bs024ty5255"
            return FakeResponse()

        monkeypatch.setattr(download_module.requests, "get", fake_get)
        monkeypatch.setenv("DOWNLOAD_PATH", str(tmp_path))

        service = DownloadService(
            {
                "id": "stanford-bs024ty5255",
                "gbl_wxsIdentifier_s": "druid:bs024ty5255",
                "dct_references_s": json.dumps(
                    {
                        "http://www.opengis.net/def/serviceType/ogc/wfs": (
                            "https://example.com/geoserver/wfs"
                        )
                    }
                ),
            }
        )

        payload = await service.ensure_generated_download("shapefile")
        file_path = tmp_path / payload["file_name"]

        assert payload["download_type"] == "shapefile"
        assert payload["content_type"] == "application/zip"
        assert file_path.exists()
        assert file_path.read_bytes() == b"zip-bytes"

    @pytest.mark.asyncio
    async def test_ensure_generated_geotiff_uses_reflect_endpoint(self, monkeypatch, tmp_path):
        """GeoTIFF generation should call the WMS reflect endpoint."""

        class FakeResponse:
            status_code = 200
            headers = {"Content-Type": "image/tiff"}
            content = b"tiff-bytes"

            def raise_for_status(self):
                return None

        def fake_get(url, params=None, timeout=30):
            assert url == "https://example.com/geoserver/wms/reflect"
            assert params is not None
            assert params["layers"] == "druid:bs024ty5255"
            assert params["format"] == "image/geotiff"
            return FakeResponse()

        monkeypatch.setattr(download_module.requests, "get", fake_get)
        monkeypatch.setenv("DOWNLOAD_PATH", str(tmp_path))

        service = DownloadService(
            {
                "id": "stanford-bs024ty5255",
                "gbl_wxsIdentifier_s": "druid:bs024ty5255",
                "dct_references_s": json.dumps(
                    {
                        "http://www.opengis.net/def/serviceType/ogc/wms": (
                            "https://example.com/geoserver/wms"
                        )
                    }
                ),
            }
        )

        payload = await service.ensure_generated_download("geotiff")
        file_path = tmp_path / payload["file_name"]
        assert payload["content_type"] == "image/geotiff"
        assert file_path.exists()
        assert file_path.read_bytes() == b"tiff-bytes"

    @pytest.mark.asyncio
    async def test_stanford_fallback_uses_geoblacklight_download(self, monkeypatch, tmp_path):
        """When WFS fails, Stanford records can fall back to EarthWorks download flow."""

        class FakeResponse:
            def __init__(self, status_code=200, headers=None, content=b"", text=""):
                self.status_code = status_code
                self.headers = headers or {}
                self.content = content
                self.text = text

            def raise_for_status(self):
                if self.status_code >= 400:
                    error = download_module.requests.HTTPError("bad response")
                    error.response = self
                    raise error
                return None

        def fake_get(url, params=None, timeout=30, headers=None):
            if "geowebservices.stanford.edu/geoserver/wfs" in url:
                return FakeResponse(status_code=400, headers={"Content-Type": "application/xml"})
            if "earthworks.stanford.edu/download/stanford-bs024ty5255" in url:
                return FakeResponse(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    text='[[["success","ready"]],"/download/file/stanford-bs024ty5255-shapefile.zip"]',
                )
            if "earthworks.stanford.edu/download/file/stanford-bs024ty5255-shapefile.zip" in url:
                return FakeResponse(
                    status_code=200,
                    headers={"Content-Type": "application/zip"},
                    content=b"zip-from-earthworks",
                )
            raise AssertionError(f"Unexpected URL called: {url}")

        monkeypatch.setattr(download_module.requests, "get", fake_get)
        monkeypatch.setenv("DOWNLOAD_PATH", str(tmp_path))

        service = DownloadService(
            {
                "id": "stanford-bs024ty5255",
                "schema_provider_s": "Stanford",
                "gbl_wxsIdentifier_s": "druid:bs024ty5255",
                "dct_references_s": json.dumps(
                    {
                        "http://www.opengis.net/def/serviceType/ogc/wfs": (
                            "https://geowebservices.stanford.edu/geoserver/wfs"
                        )
                    }
                ),
            }
        )

        payload = await service.ensure_generated_download("shapefile")
        file_path = tmp_path / payload["file_name"]
        assert file_path.exists()
        assert file_path.read_bytes() == b"zip-from-earthworks"


class TestBridgeAssetDownloads:
    @pytest.mark.asyncio
    async def test_bridge_asset_downloads_are_added_with_size_and_url(self, monkeypatch):
        # Prevent real DB access by stubbing the `databases` client.
        class FakeDB:
            is_connected = True

            async def fetch_all(self, _query):
                return [
                    {
                        "label": "Shapefile (original)",
                        "title": "Street_Centerline.zip",
                        "file_url": "https://example.com/asset/a.zip",
                        "file_mime_type": "application/zip",
                        "file_size": 3836704,
                        "position": 1,
                        "id": 1,
                    }
                ]

        monkeypatch.setattr(download_module, "database", FakeDB())

        service = DownloadService({"id": "b1g_test_resource"})
        downloads = await service.get_download_options_with_bridge_asset_downloads()

        assert downloads, "Expected at least one bridge asset download"
        assert any(
            d["url"] == "https://example.com/asset/a.zip"
            and "Shapefile (original)" in d["label"]
            and "MB" in d["label"]
            for d in downloads
        )
