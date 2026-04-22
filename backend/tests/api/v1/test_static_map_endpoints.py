"""
Tests for static map endpoints.

- /static-maps/{resource_id}: basemap-only asset.
- /static-maps/{resource_id}/geometry: geometry-overlay asset.
- /resources/{id}/static-map: compatibility redirect to the geometry asset.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.endpoint_modules.resources import router as resources_router
from app.api.v1.endpoint_modules.static_maps import router as static_maps_router
from app.services.cache_service import weak_etag_from_body


def create_valid_png_image() -> bytes:
    """Create a minimal valid PNG image for testing."""
    img = Image.new("RGBA", (2, 2), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_static_map_service_mock(*, basemap_bytes=None, geometry_bytes=None) -> MagicMock:
    """Create a service double that matches the async static map endpoint contract."""
    svc = MagicMock()
    svc.materialize_cached_variant = AsyncMock(return_value=None)
    svc.get_cached_basemap = AsyncMock(return_value=basemap_bytes)
    svc.get_cached_map = AsyncMock(return_value=geometry_bytes)
    svc.basemap_variant.return_value = "basemap"
    svc.geometry_variant.return_value = "geometry"
    svc.geometry_signature.return_value = "geometry-signature"
    svc.centered_basemap_signature.return_value = "centered-signature"
    return svc


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(static_maps_router)
    app.include_router(resources_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestStaticMapsEndpoint:
    @patch("app.api.v1.endpoint_modules.static_maps._fetch_resource_dict")
    def test_get_static_map_success_headers_and_etag(self, mock_resource, client):
        resource_id = "test-resource-id"
        png_bytes = create_valid_png_image()
        mock_resource.return_value = {"id": resource_id, "locn_geometry": "ENVELOPE(-10,10,10,-10)"}

        with patch("app.api.v1.endpoint_modules.static_maps.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock(basemap_bytes=png_bytes)
            svc_cls.return_value = svc

            resp = client.get(f"/static-maps/{resource_id}")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/png"
            assert resp.headers["etag"] == weak_etag_from_body(png_bytes)
            assert resp.headers["cache-control"].startswith("public, max-age=0")
            assert "s-maxage=" in resp.headers["cache-control"]
            svc.materialize_cached_variant.assert_awaited_once_with(
                resource_id,
                variant="basemap",
                source_signature="geometry-signature",
            )

    @patch("app.api.v1.endpoint_modules.static_maps._fetch_resource_dict")
    def test_get_static_map_if_none_match_304(self, mock_resource, client):
        resource_id = "test-resource-id"
        png_bytes = create_valid_png_image()
        mock_resource.return_value = {"id": resource_id, "locn_geometry": "ENVELOPE(-10,10,10,-10)"}

        with patch("app.api.v1.endpoint_modules.static_maps.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock(basemap_bytes=png_bytes)
            svc_cls.return_value = svc

            first = client.get(f"/static-maps/{resource_id}")
            etag = first.headers["etag"]

            second = client.get(f"/static-maps/{resource_id}", headers={"If-None-Match": etag})
            assert second.status_code == 304
            assert second.headers["etag"] == etag

    @patch("app.api.v1.endpoint_modules.static_maps._fetch_resource_dict")
    def test_get_static_map_geometry_success_headers_and_etag(self, mock_resource, client):
        resource_id = "test-resource-id"
        png_bytes = create_valid_png_image()
        mock_resource.return_value = {"id": resource_id, "locn_geometry": "ENVELOPE(-10,10,10,-10)"}

        with patch("app.api.v1.endpoint_modules.static_maps.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock(geometry_bytes=png_bytes)
            svc_cls.return_value = svc

            resp = client.get(f"/static-maps/{resource_id}/geometry")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/png"
            assert resp.headers["etag"] == weak_etag_from_body(png_bytes)
            svc.materialize_cached_variant.assert_awaited_once_with(
                resource_id,
                variant="geometry",
                source_signature="geometry-signature",
            )

    @patch("app.api.v1.endpoint_modules.static_maps._fetch_resource_dict")
    def test_get_static_map_resource_class_icon(self, mock_resource, client):
        resource_id = "test-resource-id"
        mock_resource.return_value = {
            "id": resource_id,
            "gbl_resourceClass_sm": ["Maps"],
            "locn_geometry": "ENVELOPE(-10,10,10,-10)",
            "dcat_bbox": "ENVELOPE(-10,10,10,-10)",
        }

        with patch("app.api.v1.endpoint_modules.resources.thumbnail.StaticMapService") as svc_cls:
            svc = MagicMock()
            svc.get_cached_basemap = AsyncMock(return_value=create_valid_png_image())
            svc_cls.return_value = svc

            resp = client.get(f"/static-maps/{resource_id}/resource-class-icon")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/svg+xml"

    def test_get_institution_static_map_generates_and_serves_png(self, client):
        png_bytes = create_valid_png_image()

        with patch("app.api.v1.endpoint_modules.static_maps.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock()
            svc.generate_centered_basemap.return_value = png_bytes
            svc_cls.return_value = svc

            resp = client.get(
                "/static-maps/institutions/indiana-university?lat=39.1702&lon=-86.5235&zoom=15"
            )
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/png"
            assert resp.headers["etag"] == weak_etag_from_body(png_bytes)
            svc.generate_centered_basemap.assert_called_once_with(
                "institution:indiana-university",
                latitude=39.1702,
                longitude=-86.5235,
                zoom=15,
                source_signature="centered-signature",
            )


class TestResourceStaticMapEndpoint:
    @patch("app.api.v1.endpoint_modules.resources.static_map.async_session")
    def test_resource_static_map_hot_redirect_uses_current_geometry_signature(
        self, mock_session, client
    ):
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "test-resource-id",
            "locn_geometry": "ENVELOPE(-10,10,10,-10)",
            "dcat_bbox": "ENVELOPE(-10,10,10,-10)",
        }
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute.return_value = mock_result

        with patch("app.api.v1.endpoint_modules.resources.static_map.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock()
            svc.materialize_cached_variant = AsyncMock(return_value="deadbeef" * 8)
            svc_cls.return_value = svc

            resp = client.get("/resources/test-resource-id/static-map", allow_redirects=False)

            assert resp.status_code == 302
            assert resp.headers["location"] == f"/api/v1/static-map-assets/{'deadbeef' * 8}"
            svc.materialize_cached_variant.assert_awaited_once_with(
                "test-resource-id",
                variant="geometry",
                source_signature="geometry-signature",
            )

    @patch("app.api.v1.endpoint_modules.resources.static_map.async_session")
    def test_resource_static_map_processing_placeholder_is_image_no_store(
        self, mock_session, client
    ):
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "test-resource-id",
            "locn_geometry": "ENVELOPE(-10,10,10,-10)",
            "dcat_bbox": "ENVELOPE(-10,10,10,-10)",
        }
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute.return_value = mock_result

        with patch("app.api.v1.endpoint_modules.resources.static_map.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock()
            svc_cls.return_value = svc

            resp = client.get("/resources/test-resource-id/static-map", allow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"] == "/api/v1/static-maps/test-resource-id/geometry"
            assert resp.headers["cache-control"] == "no-store"

    @patch("app.api.v1.endpoint_modules.resources.static_map.async_session")
    def test_resource_static_map_redirect_no_store_when_exists(self, mock_session, client):
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "test-resource-id",
            "locn_geometry": "ENVELOPE(-10,10,10,-10)",
            "dcat_bbox": "ENVELOPE(-10,10,10,-10)",
        }
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute.return_value = mock_result

        with patch("app.api.v1.endpoint_modules.resources.static_map.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock()
            svc_cls.return_value = svc

            resp = client.get("/resources/test-resource-id/static-map", allow_redirects=False)
            assert resp.status_code == 302
            assert resp.headers["location"] == "/api/v1/static-maps/test-resource-id/geometry"
            assert resp.headers["cache-control"] == "no-store"

    @patch("app.api.v1.endpoint_modules.resources.static_map.async_session")
    def test_resource_static_map_no_geometry_generates_global_map(self, mock_session, client):
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "no-geometry-resource",
            "locn_geometry": None,
            "dcat_bbox": None,
        }
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session_instance.execute.return_value = mock_result

        with patch("app.api.v1.endpoint_modules.resources.static_map.StaticMapService") as svc_cls:
            svc = create_static_map_service_mock()
            svc_cls.return_value = svc

            resp = client.get("/resources/no-geometry-resource/static-map", allow_redirects=False)

            assert resp.status_code == 302
            assert resp.headers["location"] == "/api/v1/static-maps/no-geometry-resource/geometry"
