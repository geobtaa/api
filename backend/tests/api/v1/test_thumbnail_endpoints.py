"""
Tests for the thumbnail endpoints.

These endpoints handle serving placeholder thumbnails and cached thumbnail images.
"""

import io
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.endpoint_modules.thumbnails import router
from app.services.cache_service import weak_etag_from_body
from app.tasks.worker import _remote_thumbnail_image_hash


def create_valid_jpeg_image() -> bytes:
    """Create a minimal valid JPEG image for testing."""
    # Create a 1x1 pixel JPEG image
    img = Image.new("RGB", (1, 1), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def app():
    """Create FastAPI app with thumbnails router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestThumbnailEndpoints:
    """Test cases for thumbnail endpoints."""

    def test_get_placeholder_thumbnail_success(self, client):
        """Test successful placeholder thumbnail retrieval."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-placeholder"] == "true"

        # Verify SVG content
        content = response.text
        assert "<svg" in content
        assert 'width="200"' in content
        assert 'height="200"' in content
        assert "Thumbnail placeholder" in content
        assert "Processing" not in content
        assert 'fill="#f8fafc"' in content
        assert 'stroke="#e5e7eb"' in content

    def test_get_placeholder_thumbnail_svg_structure(self, client):
        """Test that placeholder thumbnail has correct SVG structure."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        content = response.text

        # Check for essential SVG elements
        assert "<rect" in content
        assert "<path" in content
        assert "<circle" in content
        assert 'xmlns="http://www.w3.org/2000/svg"' in content
        assert 'role="img"' in content
        assert 'aria-label="Thumbnail placeholder"' in content

    def test_get_placeholder_thumbnail_caching_headers(self, client):
        """Test that placeholder thumbnail has proper caching headers."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        headers = response.headers

        # Verify caching headers
        assert headers["cache-control"] == "no-store"
        assert headers["x-placeholder"] == "true"
        assert headers["content-type"] == "image/svg+xml"

    def test_get_thumbnail_success(self, client):
        """Test successful thumbnail retrieval."""
        test_image_hash = "e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
            assert response.headers["etag"] == weak_etag_from_body(test_image_data)
            assert response.content == test_image_data

            # Verify service was called correctly
            mock_service_class.assert_called_once_with({})
            mock_service.get_cached_image.assert_called_once_with(test_image_hash)

    def test_get_thumbnail_resource_alias_redirect(self, client):
        """Resource-id requests should redirect to the hot immutable hash asset when known."""
        resource_id = "nyu-2451-34564"
        image_hash = "e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639"

        with (
            patch(
                "app.api.v1.endpoint_modules.thumbnails.thumbnail_alias_service.get_hash",
                new=AsyncMock(return_value=image_hash),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._current_hot_thumbnail_hash_for_resource",
                new=AsyncMock(return_value=image_hash),
            ) as mock_current_hash,
        ):
            response = client.get(f"/thumbnails/{resource_id}", follow_redirects=False)

            assert response.status_code == 302
            assert response.headers["location"] == f"/api/v1/thumbnails/{image_hash}"
            assert "max-age=3600" in response.headers["cache-control"]
            mock_current_hash.assert_not_awaited()

    def test_get_thumbnail_success_state_rehydrates_alias_redirect(self, client):
        """Cold Redis aliases should rehydrate from persisted success state."""
        resource_id = "nyu-2451-34564"
        image_hash = "e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639"

        with (
            patch(
                "app.api.v1.endpoint_modules.thumbnails.thumbnail_alias_service.get_hash",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.endpoint_modules.thumbnails.thumbnail_alias_service.set_hash",
                new=AsyncMock(return_value=True),
            ) as mock_set_hash,
            patch(
                "app.api.v1.endpoint_modules.thumbnails.thumbnail_state_service.get_state",
                new=AsyncMock(
                    return_value={
                        "state": "success",
                        "source_hash": image_hash,
                    }
                ),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._current_hot_thumbnail_hash_for_resource",
                new=AsyncMock(return_value=None),
            ) as mock_current_hash,
        ):
            response = client.get(f"/thumbnails/{resource_id}", follow_redirects=False)

            assert response.status_code == 302
            assert response.headers["location"] == f"/api/v1/thumbnails/{image_hash}"
            mock_set_hash.assert_awaited_once_with(resource_id, image_hash)
            mock_current_hash.assert_not_awaited()

    def test_get_thumbnail_not_found(self, client):
        """Test thumbnail retrieval when image is not found."""
        test_image_hash = "nonexistent_hash"

        with (
            patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._get_resource_thumbnail_response",
                new=AsyncMock(
                    side_effect=HTTPException(status_code=404, detail="Resource not found")
                ),
            ),
        ):
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 404
            assert "Resource not found" in response.json()["detail"]

    def test_get_thumbnail_missing_hash_returns_404(self, client):
        """Missing immutable asset hashes should fail fast instead of resolving as resource ids."""
        image_hash = "e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639"

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{image_hash}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Thumbnail asset not found"
            mock_service.get_cached_image.assert_awaited_once_with(image_hash)

    def test_get_thumbnail_resource_asset_fallback(self, client):
        """Test resource asset fallback when the path is a resource id, not a cached hash."""
        resource_id = "nyu-2451-34564"
        fallback_response = Response(
            content="<svg></svg>",
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store"},
        )

        with (
            patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._get_resource_thumbnail_response",
                new=AsyncMock(return_value=fallback_response),
            ) as mock_resource_response,
        ):
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{resource_id}")

            assert response.status_code == 200
            assert response.headers["content-type"] == "image/svg+xml"
            assert response.text == "<svg></svg>"
            mock_resource_response.assert_awaited_once_with(
                resource_id,
                ANY,
                variant="icon-gradient",
                not_found_placeholder=False,
            )

    def test_get_thumbnail_invalid_bridge_asset_falls_back_to_icon_variant(self, client):
        """Dead bridge thumbnail URLs should fall back to the generated icon asset."""
        resource_id = "stanford-fc944xn1421"

        with (
            patch(
                "app.api.v1.endpoint_modules.thumbnails.ImageService"
            ) as mock_cache_service_class,
            patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session") as mock_session,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context",
                new=AsyncMock(return_value=MagicMock(by_uri={}, legacy_reference_payload={})),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._get_thumbnail_asset_url",
                new=AsyncMock(return_value="https://example.com/missing-thumbnail.jpg"),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._probe_thumbnail_url",
                new=AsyncMock(return_value=False),
            ) as mock_probe,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.safe_record_thumbnail_state",
                new=AsyncMock(),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.ImageService"
            ) as mock_resource_service_class,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.THUMBNAIL_REQUEST_PROBE_ENABLED",
                True,
            ),
        ):
            mock_cache_service = MagicMock()
            mock_cache_service.get_cached_image = AsyncMock(return_value=None)
            mock_cache_service_class.return_value = mock_cache_service

            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row._mapping = {
                "id": resource_id,
                "dct_accessrights_s": "Public",
                "gbl_resourceClass_sm": ["Datasets"],
                "locn_geometry": None,
                "dcat_bbox": None,
            }
            mock_result = MagicMock()
            mock_result.fetchone.return_value = mock_row
            mock_session_instance.execute = AsyncMock(return_value=mock_result)

            mock_resource_service = MagicMock()
            mock_resource_service._get_thumbnail_source_url.return_value = None
            mock_resource_service_class.return_value = mock_resource_service

            response = client.get(f"/thumbnails/{resource_id}")

            assert response.status_code == 200
            assert response.headers["content-type"] == "image/svg+xml"
            assert "<svg" in response.text
            mock_probe.assert_awaited_once_with("https://example.com/missing-thumbnail.jpg")

    def test_get_thumbnail_valid_bridge_asset_uses_generated_thumbnail_route(self, client):
        """Valid bridge thumbnail URLs should flow through the generated thumbnail cache."""
        resource_id = "14c66cbf-b8fb-492d-b4e8-0a6cf911e25b"
        asset_url = "https://example.com/bridge-thumbnail.jpg"
        image_hash = _remote_thumbnail_image_hash(asset_url)
        test_image_data = create_valid_jpeg_image()

        with (
            patch(
                "app.api.v1.endpoint_modules.thumbnails.ImageService"
            ) as mock_cache_service_class,
            patch("app.api.v1.endpoint_modules.resources.thumbnail.async_session") as mock_session,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.fetch_distribution_context",
                new=AsyncMock(return_value=MagicMock(by_uri={}, legacy_reference_payload={})),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._get_thumbnail_asset_url",
                new=AsyncMock(return_value=asset_url),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail._probe_thumbnail_url",
                new=AsyncMock(return_value=True),
            ) as mock_probe,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.safe_record_thumbnail_state",
                new=AsyncMock(),
            ),
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.ImageService"
            ) as mock_resource_service_class,
            patch(
                "app.api.v1.endpoint_modules.resources.thumbnail.THUMBNAIL_REQUEST_PROBE_ENABLED",
                True,
            ),
        ):
            mock_cache_service = MagicMock()
            mock_cache_service.get_cached_image = AsyncMock(return_value=None)
            mock_cache_service_class.return_value = mock_cache_service

            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row._mapping = {
                "id": resource_id,
                "dct_accessrights_s": "Public",
                "gbl_resourceClass_sm": ["Maps"],
                "locn_geometry": None,
                "dcat_bbox": None,
            }
            mock_result = MagicMock()
            mock_result.fetchone.return_value = mock_row
            mock_session_instance.execute = AsyncMock(return_value=mock_result)

            mock_resource_service = MagicMock()
            mock_resource_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_resource_service._get_thumbnail_source_url.return_value = None
            mock_resource_service._standardize_iiif_url.side_effect = lambda url: url
            mock_resource_service._is_cog_url.return_value = False
            mock_resource_service._is_pmtiles_url.return_value = False
            mock_resource_service._is_manifest_url.return_value = False
            mock_resource_service_class.return_value = mock_resource_service

            response = client.get(f"/thumbnails/{resource_id}", follow_redirects=False)

            assert response.status_code == 302
            assert response.headers["location"] == f"/api/v1/thumbnails/{image_hash}"
            mock_probe.assert_awaited_once_with(asset_url)
            mock_resource_service.get_cached_image.assert_awaited_once_with(image_hash)
            mock_resource_service._get_thumbnail_source_url.assert_called_once_with()

    def test_get_thumbnail_service_error(self, client):
        """Test thumbnail retrieval with service error."""
        test_image_hash = "test_hash_123"

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(side_effect=Exception("Service error"))
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 500
            assert "Service error" in response.json()["detail"]

    def test_get_thumbnail_cache_headers(self, client):
        """Test that cached thumbnails have proper caching headers."""
        test_image_hash = "test_hash_123"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 200
            headers = response.headers

            # Verify revalidation-style caching headers for cached images
            assert headers["cache-control"].startswith("public, max-age=0")
            assert "s-maxage=" in headers["cache-control"]
            assert "stale-while-revalidate=" in headers["cache-control"]
            assert "stale-if-error=" in headers["cache-control"]
            assert headers["content-type"] == "image/jpeg"
            assert headers["etag"] == weak_etag_from_body(test_image_data)

    def test_get_thumbnail_etag_304(self, client):
        """Test conditional request support (If-None-Match -> 304)."""
        test_image_hash = "test_hash_123"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            first = client.get(f"/thumbnails/{test_image_hash}")
            assert first.status_code == 200
            etag = first.headers["etag"]

            second = client.get(
                f"/thumbnails/{test_image_hash}",
                headers={"If-None-Match": etag},
            )
            assert second.status_code == 304
            assert second.headers["etag"] == etag

    def test_get_thumbnail_different_image_hashes(self, client):
        """Test thumbnail retrieval with different image hashes."""
        test_cases = [
            "simple_hash",
            "hash_with_underscores",
            "hash-with-dashes",
            "hash_with_numbers_123",
            "hash_with_mixed_Case_456",
        ]
        test_image_data = create_valid_jpeg_image()

        for image_hash in test_cases:
            with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
                mock_service_class.return_value = mock_service

                response = client.get(f"/thumbnails/{image_hash}")

                assert response.status_code == 200
                mock_service.get_cached_image.assert_called_once_with(image_hash)

    def test_get_thumbnail_empty_hash(self, client):
        """Test thumbnail retrieval with empty hash."""
        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            response = client.get("/thumbnails/")

            # This should result in a 404 from FastAPI routing
            assert response.status_code == 404

    def test_get_thumbnail_special_characters_in_hash(self, client):
        """Test thumbnail retrieval with special characters in hash."""
        test_image_hash = "hash%20with%20encoded%20chars"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 200
            assert response.content == test_image_data

    def test_get_thumbnail_very_long_hash(self, client):
        """Test thumbnail retrieval with very long hash."""
        test_image_hash = "a" * 1000  # Very long hash
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 200
            assert response.content == test_image_data
            mock_service.get_cached_image.assert_called_once_with(test_image_hash)

    def test_get_thumbnail_multiple_calls(self, client):
        """Test multiple thumbnail retrieval calls."""
        test_image_hash = "test_hash_123"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            # Make multiple calls
            for _ in range(3):
                response = client.get(f"/thumbnails/{test_image_hash}")
                assert response.status_code == 200
                assert response.content == test_image_data

            # Verify service was called multiple times
            assert mock_service.get_cached_image.call_count == 3

    def test_get_thumbnail_service_initialization(self, client):
        """Test that ImageService is initialized with empty resource dict."""
        test_image_hash = "test_hash_123"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 200

            # Verify ImageService was initialized with empty dict
            mock_service_class.assert_called_with({})

    def test_placeholder_thumbnail_content_validation(self, client):
        """Test detailed validation of placeholder thumbnail content."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        content = response.text.strip()

        # Verify the exact structure
        # Check SVG opening tag
        assert '<svg width="200" height="200" viewBox="0 0 200 200"' in content
        assert 'xmlns="http://www.w3.org/2000/svg"' in content
        assert 'role="img"' in content
        assert 'aria-label="Thumbnail placeholder"' in content

        # Check rectangle element
        assert (
            'rect width="200" height="200" fill="#f8fafc" stroke="#e5e7eb" stroke-width="1"'
            in content
        )

        assert "<title>Thumbnail placeholder</title>" in content
        assert 'rect x="54" y="58" width="92" height="84" rx="8"' in content
        assert 'circle cx="122" cy="82" r="10"' in content
        assert "Processing" not in content

        # Check SVG closing tag - more flexible matching
        assert "</svg>" in content

    def test_placeholder_thumbnail_colors_and_styling(self, client):
        """Test placeholder thumbnail colors and styling."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        content = response.text

        # Verify color scheme
        assert "#f8fafc" in content  # Light gray background
        assert "#e5e7eb" in content  # Border color
        assert "#e2e8f0" in content  # Icon panel color
        assert "#94a3b8" in content  # Icon glyph color

        # Verify font styling
        assert 'role="img"' in content
        assert 'aria-label="Thumbnail placeholder"' in content

    def test_get_thumbnail_content_type_validation(self, client):
        """Test that thumbnails return correct content types."""
        test_image_hash = "test_hash_123"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            # Test cached thumbnail
            response = client.get(f"/thumbnails/{test_image_hash}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"

        # Test placeholder thumbnail
        response = client.get("/thumbnails/placeholder")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"

    def test_get_thumbnail_response_size(self, client):
        """Test that thumbnail responses have correct content size."""
        test_image_hash = "test_hash_123"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 200
            assert len(response.content) == len(test_image_data)

        # Test placeholder size
        response = client.get("/thumbnails/placeholder")
        assert response.status_code == 200
        assert len(response.content) > 0  # SVG should have content

    def test_get_thumbnail_error_handling_types(self, client):
        """Test different types of errors in thumbnail retrieval."""
        test_image_hash = "test_hash_123"

        error_cases = [
            ("Connection Error", "Connection timeout"),
            ("Value Error", "Invalid image hash format"),
            ("Runtime Error", "Service unavailable"),
            ("Attribute Error", "Missing attribute"),
        ]

        for _error_type, error_message in error_cases:
            with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_cached_image = AsyncMock(side_effect=Exception(error_message))
                mock_service_class.return_value = mock_service

                response = client.get(f"/thumbnails/{test_image_hash}")

                assert response.status_code == 500
                assert error_message in response.json()["detail"]

    def test_placeholder_thumbnail_accessibility(self, client):
        """Test that placeholder thumbnail is accessible and well-formed."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        content = response.text

        # Verify it's well-formed XML/SVG
        assert content.startswith("<svg")
        assert content.endswith("</svg>")

        # Verify accessibility features
        assert 'xmlns="http://www.w3.org/2000/svg"' in content  # Proper namespace
        assert 'width="200"' in content  # Explicit dimensions
        assert 'height="200"' in content

        # Verify the placeholder has an accessible label without visible processing text
        assert "Thumbnail placeholder" in content
        assert "Processing" not in content
