"""
Tests for COG thumbnail generation in the worker module.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.thumbnail_policy import source_signature
from app.tasks.worker import (
    _cog_thumbnail_image_hash,
    _generate_cog_thumbnail_bytes,
    _is_cog_url,
)


def _valid_png_bytes() -> bytes:
    """Valid PNG for tests (must be >= 100 bytes for task validation)."""
    img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestCogThumbnailHelpers:
    """Test COG thumbnail helper functions."""

    def test_cog_thumbnail_image_hash_deterministic(self):
        """Hash is deterministic for same URL."""
        url = "https://example.com/cog.tif"
        h1 = _cog_thumbnail_image_hash(url)
        h2 = _cog_thumbnail_image_hash(url)
        assert h1 == h2
        assert len(h1) == 64
        assert all(c in "0123456789abcdef" for c in h1)

    def test_cog_thumbnail_image_hash_includes_prefix(self):
        """Hash incorporates COG prefix to avoid collision with regular image hashes."""
        url = "https://example.com/cog.tif"
        expected = source_signature(url)
        assert _cog_thumbnail_image_hash(url) == expected

    def test_cog_thumbnail_image_hash_different_urls_different_hashes(self):
        """Different URLs produce different hashes."""
        h1 = _cog_thumbnail_image_hash("https://example.com/a.tif")
        h2 = _cog_thumbnail_image_hash("https://example.com/b.tif")
        assert h1 != h2

    def test_is_cog_url_tif_extension(self):
        """Detect COG URLs by .tif/.tiff extension."""
        assert _is_cog_url("https://example.com/raster.tif") is True
        assert _is_cog_url("https://example.com/raster.TIFF") is True

    def test_is_cog_url_display_raster(self):
        """Detect display_raster pattern."""
        assert _is_cog_url("https://geodata.lib.princeton.edu/13/f5/58/display_raster.tif") is True

    def test_is_cog_url_geotiff_in_path(self):
        """Detect geotiff in URL path."""
        assert _is_cog_url("https://example.com/geotiff/file.tif") is True

    def test_is_cog_url_rejects_non_cog(self):
        """Reject non-COG URLs."""
        assert _is_cog_url("https://example.com/image.jpg") is False
        assert _is_cog_url("https://example.com/manifest.json") is False
        assert _is_cog_url("") is False


try:
    import rio_tiler  # noqa: F401

    RIO_TILER_AVAILABLE = True
except ImportError:
    RIO_TILER_AVAILABLE = False


@pytest.mark.skipif(not RIO_TILER_AVAILABLE, reason="rio-tiler not installed")
class TestGenerateCogThumbnailBytes:
    """Test _generate_cog_thumbnail_bytes."""

    def test_returns_none_on_rio_tiler_failure(self):
        """Returns None when rio-tiler raises."""
        with patch("rio_tiler.io.Reader") as mock_reader_cls:
            mock_reader_cls.side_effect = Exception("Network error")
            result = _generate_cog_thumbnail_bytes("https://example.com/cog.tif")
            assert result is None

    def test_returns_none_when_preview_empty(self):
        """Returns None when preview returns no data."""
        mock_img = MagicMock()
        mock_img.data = None
        mock_img.mask = None
        with patch("rio_tiler.io.Reader") as mock_reader_cls:
            mock_src = MagicMock()
            mock_src.preview.return_value = mock_img
            mock_reader_cls.return_value.__enter__.return_value = mock_src
            result = _generate_cog_thumbnail_bytes("https://example.com/cog.tif")
            assert result is None

    def test_returns_png_bytes_on_success(self):
        """Returns valid PNG bytes when rio-tiler succeeds."""
        import numpy as np

        png_bytes = _valid_png_bytes()
        mock_img = MagicMock()
        mock_img.data = np.zeros((3, 64, 64), dtype=np.uint8)
        mock_img.mask = np.zeros((64, 64), dtype=np.uint8)

        with (
            patch("rio_tiler.io.Reader") as mock_reader_cls,
            patch("rio_tiler.utils.render", return_value=png_bytes) as mock_render,
        ):
            mock_src = MagicMock()
            mock_src.preview.return_value = mock_img
            mock_reader_cls.return_value.__enter__.return_value = mock_src

            result = _generate_cog_thumbnail_bytes("https://example.com/cog.tif")
            assert result == png_bytes
            mock_render.assert_called_once()
