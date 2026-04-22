"""
Tests for resource thumbnail endpoint (/resources/{id}/thumbnail).
Includes COG thumbnail flow.
"""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.endpoint_modules.resources import router as resources_router
from app.tasks.worker import (
    _cog_thumbnail_image_hash,
    _pmtiles_thumbnail_image_hash,
    _remote_thumbnail_image_hash,
)


def _valid_png_bytes() -> bytes:
    """Valid PNG for tests (detected as image/png by _detect_image_type)."""
    img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _large_jpeg_bytes() -> bytes:
    """Large JPEG used to verify no-cache normalization for remote images."""
    img = Image.new("RGB", (4500, 4300), color=(200, 180, 120))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(resources_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def patch_thumbnail_side_effects():
    with (
        patch(
            "app.api.v1.endpoint_modules.resources.thumbnail.safe_record_thumbnail_state",
            new=AsyncMock(),
        ) as mock_state,
        patch(
            "app.api.v1.endpoint_modules.resources.thumbnail.acquire_thumbnail_queue_slot",
            return_value=True,
        ) as mock_queue_slot,
    ):
        yield {"state": mock_state, "queue_slot": mock_queue_slot}


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

    def test_resource_thumbnail_alias_redirect_short_circuits(self, client):
        """Hot resource-id requests should redirect straight to the immutable asset."""
        resource_id = "test-fast-alias"
        image_hash = "e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639"

        with (
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.thumbnail_alias_service.get_hash",
                new=AsyncMock(return_value=image_hash),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.ImageService"
            ) as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.has_cached_image = AsyncMock(return_value=True)
            mock_service_class.return_value = mock_service

            response = client.get(f"/resources/{resource_id}/thumbnail", allow_redirects=False)

            assert response.status_code == 302
            assert response.headers["location"] == f"/api/v1/thumbnails/{image_hash}"
            assert "max-age=3600" in response.headers["cache-control"]
            mock_service_class.assert_called_once_with({})
            mock_service.has_cached_image.assert_awaited_once_with(image_hash)

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_native_thumbnail_source_takes_priority_over_bridge_asset(
        self, mock_fetch_dist, mock_session, client, patch_thumbnail_side_effects
    ):
        """Prefer native IIIF/image sources over bridge assets when both exist."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        resource_id = "test-native-over-asset"
        iiif_url = "https://example.com/iiif/2/resource/full/!800,800/0/default.jpg"
        asset_url = "https://example.com/bridge-thumbnail.jpg"
        refs = f'{{"http://iiif.io/api/image": "{iiif_url}"}}'
        mock_row = _resource_row(resource_id, refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_fetch_dist.return_value = MagicMock(by_uri={}, legacy_reference_payload={})

        image_hash = _remote_thumbnail_image_hash(iiif_url)
        png_bytes = _valid_png_bytes()

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._get_thumbnail_asset_url",
                new=AsyncMock(return_value=asset_url),
            ) as mock_get_asset,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._probe_thumbnail_url",
                new=AsyncMock(return_value=True),
            ) as mock_probe,
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = iiif_url
            svc._is_cog_url.return_value = False
            svc._is_pmtiles_url.return_value = False
            svc._is_manifest_url.return_value = False
            svc._standardize_iiif_url.side_effect = lambda url: url
            svc.get_cached_image = AsyncMock(return_value=png_bytes)
            mock_svc_cls.return_value = svc

            resp = client.get(f"/resources/{resource_id}/thumbnail", allow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"] == f"/api/v1/thumbnails/{image_hash}"
            mock_get_asset.assert_not_awaited()
            mock_probe.assert_not_awaited()
            payload = patch_thumbnail_side_effects["state"].await_args.args[0]
            assert payload.state == "success"
            assert payload.source_hash == image_hash

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_cog_queues_generate_task_returns_placeholder(
        self, mock_fetch_dist, mock_session, client, patch_thumbnail_side_effects
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
            mock_task.delay.return_value = SimpleNamespace(id="cog-task-1")
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
            payload = patch_thumbnail_side_effects["state"].await_args.args[0]
            assert payload.state == "queued"
            assert payload.queue_task_id == "cog-task-1"
            assert payload.source_type == "cog"

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_cog_redirects_when_cached(
        self, mock_fetch_dist, mock_session, client, patch_thumbnail_side_effects
    ):
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
            payload = patch_thumbnail_side_effects["state"].await_args.args[0]
            assert payload.state == "success"
            assert payload.source_hash == image_hash


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

        png_bytes = _valid_png_bytes()

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
            image = Image.open(io.BytesIO(resp.content))
            assert image.format == "PNG"
            assert image.size == (64, 64)

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_no_cache_cog_fallback_to_resource_class_icon_on_failure(
        self, mock_fetch_dist, mock_session, client
    ):
        """No-cache COG falls back to resource-class icon when generation fails."""
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
                "app.api.v1.endpoint_modules.resources.thumbnail.StaticMapService"
            ) as mock_map_service_cls,
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
            map_svc = MagicMock()
            map_svc.get_cached_basemap = AsyncMock(return_value=None)
            map_svc.generate_basemap.return_value = None
            map_svc.generate_global_basemap.return_value = None
            mock_map_service_cls.return_value = map_svc

            resp = client.get("/resources/test-cog/thumbnail/no-cache")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/svg+xml"
            assert "<svg" in resp.text


class TestResourceThumbnailPmtilesFlow:
    """Test PMTiles thumbnail handling in resource thumbnail endpoint."""

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_pmtiles_queues_generate_task_returns_placeholder(
        self, mock_fetch_dist, mock_session, client, patch_thumbnail_side_effects
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
            mock_task.delay.return_value = SimpleNamespace(id="pmtiles-task-1")
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
            payload = patch_thumbnail_side_effects["state"].await_args.args[0]
            assert payload.state == "queued"
            assert payload.queue_task_id == "pmtiles-task-1"
            assert payload.source_type == "pmtiles"

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_pmtiles_redirects_when_cached(
        self, mock_fetch_dist, mock_session, client, patch_thumbnail_side_effects
    ):
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
            payload = patch_thumbnail_side_effects["state"].await_args.args[0]
            assert payload.state == "success"
            assert payload.source_hash == image_hash

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_missing_thumbnail_source_uses_basemap_background(
        self, mock_fetch_dist, mock_session, client, patch_thumbnail_side_effects
    ):
        """When no thumbnail source exists, the icon fallback can include a basemap background."""
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_row = _resource_row("test-no-source", "{}")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_fetch_dist.return_value = MagicMock(by_uri={}, legacy_reference_payload={})

        with (
            patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.StaticMapService"
            ) as mock_map_service_cls,
        ):
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = None
            mock_svc_cls.return_value = svc

            map_svc = MagicMock()
            map_svc.get_cached_basemap = AsyncMock(return_value=_valid_png_bytes())
            mock_map_service_cls.return_value = map_svc

            resp = client.get("/resources/test-no-source/thumbnail")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/svg+xml"
            assert "data:image/png;base64," in resp.text
            payload = patch_thumbnail_side_effects["state"].await_args.args[0]
            assert payload.state == "placeheld"
            assert payload.source_url is None

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_pmtiles_skip_marker_marks_placeheld(
        self, mock_fetch_dist, mock_session, client, patch_thumbnail_side_effects
    ):
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        pmtiles_url = "https://example.com/vector.pmtiles"
        refs = f'{{"https://github.com/protomaps/PMTiles": "{pmtiles_url}"}}'
        mock_row = _resource_row("test-pmtiles-skip", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_ctx = MagicMock()
        mock_ctx.by_uri = {"https://github.com/protomaps/PMTiles": [MagicMock(url=pmtiles_url)]}
        mock_ctx.legacy_reference_payload = {"https://github.com/protomaps/PMTiles": pmtiles_url}
        mock_fetch_dist.return_value = mock_ctx

        image_hash = _pmtiles_thumbnail_image_hash(pmtiles_url)

        with patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls:
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = pmtiles_url
            svc._is_cog_url.return_value = False
            svc._is_pmtiles_url.return_value = True
            svc._is_manifest_url.return_value = False
            svc.get_cached_image = AsyncMock(return_value=None)
            svc.is_pmtiles_skip_cached.return_value = True
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-pmtiles-skip/thumbnail")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/svg+xml"
            payload = patch_thumbnail_side_effects["state"].await_args.args[0]
            assert payload.state == "placeheld"
            assert payload.source_hash == image_hash


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
            image = Image.open(io.BytesIO(resp.content))
            assert image.format == "PNG"
            assert image.size == (64, 64)

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_no_cache_pmtiles_fallback_to_resource_class_icon_on_failure(
        self, mock_fetch_dist, mock_session, client
    ):
        """
        No-cache PMTiles falls back to resource-class icon when generation fails.
        """
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
                "app.api.v1.endpoint_modules.resources.thumbnail.StaticMapService"
            ) as mock_map_service_cls,
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
            map_svc = MagicMock()
            map_svc.get_cached_basemap = AsyncMock(return_value=None)
            map_svc.generate_basemap.return_value = None
            map_svc.generate_global_basemap.return_value = None
            mock_map_service_cls.return_value = map_svc

            resp = client.get("/resources/test-pmtiles/thumbnail/no-cache")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/svg+xml"
            assert "<svg" in resp.text


class TestResourceThumbnailNoCacheRemoteFlow:
    """Test direct-image handling in the no-cache thumbnail endpoint."""

    @patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session")
    @patch("app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context")
    def test_no_cache_remote_image_resizes_large_jpeg(self, mock_fetch_dist, mock_session, client):
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        source_url = "https://example.com/large-thumb.jpg"
        refs = f'{{"http://schema.org/thumbnailUrl": "{source_url}"}}'
        mock_row = _resource_row("test-remote", refs)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute = AsyncMock(return_value=mock_result)

        mock_fetch_dist.return_value = MagicMock(by_uri={}, legacy_reference_payload={})

        large_jpeg = _large_jpeg_bytes()

        with patch("app.api.v1.endpoint_modules.resources.thumbnail.ImageService") as mock_svc_cls:
            svc = MagicMock()
            svc._get_thumbnail_source_url.return_value = source_url
            svc._is_cog_url.return_value = False
            svc._is_pmtiles_url.return_value = False
            svc._is_manifest_url.return_value = False
            svc._standardize_iiif_url.side_effect = lambda url: url
            svc.download_image = AsyncMock(return_value=large_jpeg)
            mock_svc_cls.return_value = svc

            resp = client.get("/resources/test-remote/thumbnail/no-cache")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/jpeg"
            image = Image.open(io.BytesIO(resp.content))
            assert image.format == "JPEG"
            assert max(image.size) <= 512
            assert len(resp.content) < len(large_jpeg)
