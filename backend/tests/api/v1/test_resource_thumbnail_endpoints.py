"""
Tests for resource thumbnail endpoint (/resources/{id}/thumbnail).
Includes COG thumbnail flow.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.endpoint_modules.resources import router as resources_router
from app.tasks.worker import _cog_thumbnail_image_hash, _pmtiles_thumbnail_image_hash


def _valid_png_bytes() -> bytes:
    """Valid PNG for tests (detected as image/png by _detect_image_type)."""
    img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(resources_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _resource_row(id: str, dct_references_s: str, locn_geometry: str | None = None):
    """Build mock resource row."""
    row = MagicMock()
    row._mapping = {
        "id": id,
        "dct_references_s": dct_references_s,
        "locn_geometry": locn_geometry or "ENVELOPE(-97.7, -97.6, 30.2, 30.3)",
        "dcat_bbox": locn_geometry or "ENVELOPE(-97.7, -97.6, 30.2, 30.3)",
        "dct_accessrights_s": "Public",
        "gbl_resourceClass_sm": ["Maps"],
    }
    return row


class TestResourceThumbnailCogFlow:
    """Test COG thumbnail handling in resource thumbnail endpoint."""

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_cog_queues_generate_task_returns_placeholder(
        self, mock_fetch_dist, mock_session, client
    ):
        """When source is COG and not cached, queue task and return placeholder."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        cog_url = "https://geodata.lib.princeton.edu/13/f5/58/display_raster.tif"
        refs = f'{{"https://github.com/cogeotiff/cog-spec": "{cog_url}"}}'
        mock_row = _resource_row("utaustin_121171", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/cogeotiff/cog-spec": [MagicMock(url=cog_url)]}
        mock_ctx.legacy_reference_payload = {"https://github.com/cogeotiff/cog-spec": cog_url}
        mock_fetch_dist.return_value = mock_ctx

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.generate_cog_thumbnail"
            ) as mock_task,
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = cog_url
            svc._is_cog_url.return_value = True
            svc._is_pmtiles_url.return_value = False
            svc._is_manifest_url.return_value = False
            svc.get_cached_image = AsyncMock(return_value=None)
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/utaustin_121171/thumbnail")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/svg+xml"
            assert "Generating thumbnail" in resp.text
            mock_task.delay.assert_called_once_with(cog_url, "utaustin_121171")

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_cog_redirects_when_cached(self, mock_fetch_dist, mock_session, client):
        """When COG thumbnail is cached, redirect to thumbnails/{hash}."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        cog_url = "https://example.com/cog.tif"
        refs = f'{{"https://github.com/cogeotiff/cog-spec": "{cog_url}"}}'
        mock_row = _resource_row("test-cog-resource", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/cogeotiff/cog-spec": [MagicMock(url=cog_url)]}
        mock_ctx.legacy_reference_payload = {"https://github.com/cogeotiff/cog-spec": cog_url}
        mock_fetch_dist.return_value = mock_ctx

        image_hash = _cog_thumbnail_image_hash(cog_url)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls:
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = cog_url
            svc._is_cog_url.return_value = True
            svc._is_manifest_url.return_value = False
            svc.get_cached_image = AsyncMock(return_value=png_bytes)
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-cog-resource/thumbnail", allow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"] == f"/api/v1/thumbnails/{image_hash}"


class TestResourceThumbnailNoCacheCogFlow:
    """Test COG handling in no-cache thumbnail endpoint."""

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_no_cache_cog_returns_png_on_success(self, mock_fetch_dist, mock_session, client):
        """No-cache with COG returns PNG when generation succeeds."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        cog_url = "https://example.com/cog.tif"
        refs = f'{{"https://github.com/cogeotiff/cog-spec": "{cog_url}"}}'
        mock_row = _resource_row("test-cog", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/cogeotiff/cog-spec": [MagicMock(url=cog_url)]}
        mock_fetch_dist.return_value = mock_ctx

        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._generate_cog_thumbnail_bytes",
                return_value=png_bytes,
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.asyncio.to_thread",
                side_effect=lambda f, *a: f(*a),
            ),
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = cog_url
            svc._is_cog_url.return_value = True
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-cog/thumbnail/no-cache")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/png"
            assert resp.content == png_bytes

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_no_cache_cog_fallback_to_static_map_on_failure(
        self, mock_fetch_dist, mock_session, client
    ):
        """No-cache COG falls back to static map when generation fails."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        cog_url = "https://example.com/cog.tif"
        refs = f'{{"https://github.com/cogeotiff/cog-spec": "{cog_url}"}}'
        mock_row = _resource_row("test-cog", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/cogeotiff/cog-spec": [MagicMock(url=cog_url)]}
        mock_fetch_dist.return_value = mock_ctx

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._generate_cog_thumbnail_bytes",
                return_value=None,
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.asyncio.to_thread",
                side_effect=lambda f, *a: f(*a),
            ),
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = cog_url
            svc._is_cog_url.return_value = True
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-cog/thumbnail/no-cache", allow_redirects=False)
            assert resp.status_code == 302
            assert "/static-map/no-cache" in resp.headers["location"]


class TestResourceThumbnailPmtilesFlow:
    """Test PMTiles thumbnail handling in resource thumbnail endpoint."""

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_pmtiles_queues_generate_task_returns_placeholder(
        self, mock_fetch_dist, mock_session, client
    ):
        """When source is PMTiles and not cached, queue task and return placeholder."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        pmtiles_url = "https://geodata.lib.princeton.edu/fe/d2/80/display_vector.pmtiles"
        refs = f'{{"https://github.com/protomaps/PMTiles": "{pmtiles_url}"}}'
        mock_row = _resource_row("b1g_PJxxfKgpqpUT", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/protomaps/PMTiles": [MagicMock(url=pmtiles_url)]}
        mock_ctx.legacy_reference_payload = {"https://github.com/protomaps/PMTiles": pmtiles_url}
        mock_fetch_dist.return_value = mock_ctx

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.generate_pmtiles_thumbnail"
            ) as mock_task,
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = pmtiles_url
            svc._is_cog_url.return_value = False
            svc._is_pmtiles_url.return_value = True
            svc._is_manifest_url.return_value = False
            svc.get_cached_image = AsyncMock(return_value=None)
            svc.is_pmtiles_skip_cached.return_value = False
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/b1g_PJxxfKgpqpUT/thumbnail")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/svg+xml"
            assert "Generating thumbnail" in resp.text
            mock_task.delay.assert_called_once_with(pmtiles_url, "b1g_PJxxfKgpqpUT")

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_pmtiles_redirects_when_cached(self, mock_fetch_dist, mock_session, client):
        """When PMTiles thumbnail is cached, redirect to thumbnails/{hash}."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        pmtiles_url = "https://example.com/tiles.pmtiles"
        refs = f'{{"https://github.com/protomaps/PMTiles": "{pmtiles_url}"}}'
        mock_row = _resource_row("test-pmtiles-resource", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/protomaps/PMTiles": [MagicMock(url=pmtiles_url)]}
        mock_ctx.legacy_reference_payload = {"https://github.com/protomaps/PMTiles": pmtiles_url}
        mock_fetch_dist.return_value = mock_ctx

        image_hash = _pmtiles_thumbnail_image_hash(pmtiles_url)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls:
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = pmtiles_url
            svc._is_cog_url.return_value = False
            svc._is_pmtiles_url.return_value = True
            svc._is_manifest_url.return_value = False
            svc.get_cached_image = AsyncMock(return_value=png_bytes)
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-pmtiles-resource/thumbnail", allow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"] == f"/api/v1/thumbnails/{image_hash}"


class TestResourceThumbnailNoCachePmtilesFlow:
    """Test PMTiles handling in no-cache thumbnail endpoint."""

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_no_cache_pmtiles_returns_png_on_success(self, mock_fetch_dist, mock_session, client):
        """No-cache with PMTiles returns PNG when generation succeeds (raster)."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        pmtiles_url = "https://example.com/raster.pmtiles"
        refs = f'{{"https://github.com/protomaps/PMTiles": "{pmtiles_url}"}}'
        mock_row = _resource_row("test-pmtiles", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/protomaps/PMTiles": [MagicMock(url=pmtiles_url)]}
        mock_fetch_dist.return_value = mock_ctx

        png_bytes = _valid_png_bytes()

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._generate_pmtiles_thumbnail_bytes",
                return_value=png_bytes,
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.asyncio.to_thread",
                side_effect=lambda f, *a: f(*a),
            ),
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = pmtiles_url
            svc._is_cog_url.return_value = False
            svc._is_pmtiles_url.return_value = True
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-pmtiles/thumbnail/no-cache")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/png"
            assert resp.content == png_bytes

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_no_cache_pmtiles_fallback_to_static_map_on_failure(
        self, mock_fetch_dist, mock_session, client
    ):
        """No-cache PMTiles falls back to static map when generation fails (vector/empty)."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        pmtiles_url = "https://example.com/vector.pmtiles"
        refs = f'{{"https://github.com/protomaps/PMTiles": "{pmtiles_url}"}}'
        mock_row = _resource_row("test-pmtiles", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/protomaps/PMTiles": [MagicMock(url=pmtiles_url)]}
        mock_fetch_dist.return_value = mock_ctx

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._generate_pmtiles_thumbnail_bytes",
                return_value=None,
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.asyncio.to_thread",
                side_effect=lambda f, *a: f(*a),
            ),
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = pmtiles_url
            svc._is_cog_url.return_value = False
            svc._is_pmtiles_url.return_value = True
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-pmtiles/thumbnail/no-cache", allow_redirects=False)
            assert resp.status_code == 302
            assert "/static-map/no-cache" in resp.headers["location"]
