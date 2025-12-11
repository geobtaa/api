"""
Tests for the thumbnail endpoints.

These endpoints handle serving placeholder thumbnails and cached thumbnail images.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.endpoint_modules.thumbnails import router


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
        assert response.headers["cache-control"] == "public, max-age=3600"
        assert response.headers["x-placeholder"] == "true"

        # Verify SVG content
        content = response.text
        assert "<svg" in content
        assert 'width="200"' in content
        assert 'height="200"' in content
        assert "Thumbnail" in content
        assert "Processing..." in content
        assert 'fill="#f0f0f0"' in content
        assert 'stroke="#cccccc"' in content

    def test_get_placeholder_thumbnail_svg_structure(self, client):
        """Test that placeholder thumbnail has correct SVG structure."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        content = response.text

        # Check for essential SVG elements
        assert "<rect" in content
        assert "<text" in content
        assert 'xmlns="http://www.w3.org/2000/svg"' in content
        assert 'font-family="Arial, sans-serif"' in content
        assert 'text-anchor="middle"' in content

    def test_get_placeholder_thumbnail_caching_headers(self, client):
        """Test that placeholder thumbnail has proper caching headers."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        headers = response.headers

        # Verify caching headers
        assert headers["cache-control"] == "public, max-age=3600"
        assert headers["x-placeholder"] == "true"
        assert headers["content-type"] == "image/svg+xml"

    def test_get_thumbnail_success(self, client):
        """Test successful thumbnail retrieval."""
        test_image_hash = "test_hash_123"
        test_image_data = create_valid_jpeg_image()

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=test_image_data)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert response.headers["cache-control"] == "public, max-age=31536000"
            assert response.content == test_image_data

            # Verify service was called correctly
            mock_service_class.assert_called_once_with({})
            mock_service.get_cached_image.assert_called_once_with(test_image_hash)

    def test_get_thumbnail_not_found(self, client):
        """Test thumbnail retrieval when image is not found."""
        test_image_hash = "nonexistent_hash"

        with patch("app.api.v1.endpoint_modules.thumbnails.ImageService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_cached_image = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            response = client.get(f"/thumbnails/{test_image_hash}")

            assert response.status_code == 404
            assert "Image not found" in response.json()["detail"]

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

            # Verify long-term caching headers for cached images
            assert headers["cache-control"] == "public, max-age=31536000"
            assert headers["content-type"] == "image/jpeg"

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
        assert '<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">' in content

        # Check rectangle element
        assert (
            'rect width="200" height="200" fill="#f0f0f0" stroke="#cccccc" stroke-width="1"'
            in content
        )

        # Check first text element (Thumbnail) - more flexible matching
        assert 'text x="100" y="100"' in content
        assert 'font-size="14"' in content
        assert "Thumbnail" in content

        # Check second text element (Processing...) - more flexible matching
        assert 'text x="100" y="120"' in content
        assert 'font-size="12"' in content
        assert "Processing..." in content

        # Check SVG closing tag - more flexible matching
        assert "</svg>" in content

    def test_placeholder_thumbnail_colors_and_styling(self, client):
        """Test placeholder thumbnail colors and styling."""
        response = client.get("/thumbnails/placeholder")

        assert response.status_code == 200
        content = response.text

        # Verify color scheme
        assert "#f0f0f0" in content  # Light gray background
        assert "#cccccc" in content  # Border color
        assert "#666666" in content  # Main text color
        assert "#999999" in content  # Secondary text color

        # Verify font styling
        assert 'font-family="Arial, sans-serif"' in content
        assert 'text-anchor="middle"' in content

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

        # Verify text is readable
        assert "Thumbnail" in content
        assert "Processing..." in content
