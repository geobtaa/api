import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.endpoint_modules.static_maps import router
from app.services import native_static_maps
from app.services.static_map_service import StaticMapService


def test_native_signatures_change_with_revision_and_dimensions(monkeypatch):
    monkeypatch.setenv("STATIC_MAP_RENDERER_URL", "http://renderer:8080")
    small = StaticMapService(640, 320)
    first = small.centered_basemap_signature(latitude=39, longitude=-86, zoom=15)
    assert first != StaticMapService(800, 600).centered_basemap_signature(
        latitude=39, longitude=-86, zoom=15
    )
    monkeypatch.setenv("STATIC_MAP_RENDER_REVISION", "new-style")
    assert first != small.centered_basemap_signature(latitude=39, longitude=-86, zoom=15)
    assert small.basemap_variant() == "native_basemap_v1"


@pytest.mark.parametrize(
    "query", ["lat=nan&lon=0", "lat=90&lon=0", "lat=0&lon=181", "lat=0&lon=0&zoom=30"]
)
def test_campus_rejects_bad_camera(query):
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).get("/static-maps/institutions/test?" + query).status_code == 422


def test_remote_failure_does_not_publish_or_use_carto(monkeypatch):
    monkeypatch.setenv("STATIC_MAP_RENDERER_URL", "http://renderer:8080")
    service = StaticMapService()
    service.map_cache = MagicMock()
    with (
        patch.object(native_static_maps, "reuse_geometry", return_value=None),
        patch.object(native_static_maps.requests, "post", side_effect=RuntimeError("unavailable")),
        patch.object(service, "materialize_asset_sync") as persist,
    ):
        with pytest.raises(RuntimeError, match="unavailable"):
            service.generate_map("record", "ENVELOPE(-90,-89,40,39)")
        persist.assert_not_called()


def test_wrong_size_png_is_not_published(monkeypatch):
    monkeypatch.setenv("STATIC_MAP_RENDERER_URL", "http://renderer:8080")
    output = io.BytesIO()
    Image.new("RGB", (2, 2)).save(output, "PNG")
    response = MagicMock(content=output.getvalue())
    service = StaticMapService()
    service.map_cache = MagicMock()
    with (
        patch.object(native_static_maps, "reuse_geometry", return_value=None),
        patch.object(native_static_maps.requests, "post", return_value=response),
        patch.object(service, "materialize_asset_sync") as persist,
    ):
        with pytest.raises(ValueError, match="dimensions"):
            service.generate_map("record", "ENVELOPE(-90,-89,40,39)")
        persist.assert_not_called()


def test_identical_geometry_reuses_bytes_without_rendering():
    service = MagicMock()
    service.geometry_signature.return_value = "geometry-and-dimensions"
    service.geometry_variant.return_value = "native_geometry_v1"
    service.get_cached_asset_sync.return_value = b"existing PNG"
    service.materialize_asset_sync.return_value = "digest"
    with (
        patch.object(
            native_static_maps, "get_durable_visual_asset_hash_for_signature", return_value="digest"
        ),
        patch.object(
            native_static_maps, "get_durable_visual_asset_hash_for_resource", return_value="digest"
        ),
        patch.object(native_static_maps, "_generate_uncached") as render,
    ):
        assert (
            native_static_maps.generate(service, "different-record", "POINT(1 2)")
            == b"existing PNG"
        )
    render.assert_not_called()
    assert service.materialize_asset_sync.call_args.args[0] == "different-record"


def test_concurrent_identical_geometry_is_not_rendered_twice():
    service = MagicMock()
    service.map_cache.set.return_value = False
    with (
        patch.object(native_static_maps, "reuse_geometry", return_value=None),
        patch.object(native_static_maps, "_generate_uncached") as render,
    ):
        with pytest.raises(RuntimeError, match="already rendering"):
            native_static_maps.generate(service, "record", "POINT(1 2)")
    render.assert_not_called()
    service.map_cache.eval.assert_not_called()


def test_cache_only_storage_does_not_require_a_database_body():
    output = io.BytesIO()
    Image.new("RGB", (400, 300)).save(output, "PNG")
    data = output.getvalue()
    service = StaticMapService(400, 300)
    service.map_cache = MagicMock()
    response = MagicMock(content=data, status_code=200)
    with (
        patch.object(native_static_maps.requests, "post", return_value=response),
        patch.object(native_static_maps, "durable_visual_asset_enabled", return_value=False),
        patch.object(native_static_maps, "get_durable_visual_asset") as durable_read,
        patch.object(native_static_maps, "cache_visual_asset", return_value=False),
        patch.object(service, "materialize_asset_sync", return_value="a" * 64),
    ):
        assert (
            native_static_maps.generate(service, "institution:test", center=[0, 0], zoom=3) == data
        )
    durable_read.assert_not_called()
