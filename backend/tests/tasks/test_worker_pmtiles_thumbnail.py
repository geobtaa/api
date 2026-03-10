"""
Tests for PMTiles thumbnail generation in the worker module.
"""

import gzip
import hashlib
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.tasks.worker import (
    PMTILES_THUMBNAIL_PREFIX,
    _extract_mvt_points,
    _generate_pmtiles_thumbnail_bytes,
    _http_get_bytes,
    _is_pmtiles_url,
    _pmtiles_thumbnail_image_hash,
    _render_mvt_to_png,
    generate_pmtiles_thumbnail,
)

try:
    import mapbox_vector_tile  # noqa: F401

    MVT_AVAILABLE = True
except ImportError:
    MVT_AVAILABLE = False

try:
    import pmtiles  # noqa: F401

    PMTILES_AVAILABLE = True
except ImportError:
    PMTILES_AVAILABLE = False


def _valid_png_bytes() -> bytes:
    """Valid PNG for tests (must be >= 100 bytes for task validation)."""
    img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPmtilesThumbnailHelpers:
    """Test PMTiles thumbnail helper functions."""

    def test_pmtiles_thumbnail_image_hash_deterministic(self):
        """Hash is deterministic for same URL."""
        url = "https://example.com/tiles.pmtiles"
        h1 = _pmtiles_thumbnail_image_hash(url)
        h2 = _pmtiles_thumbnail_image_hash(url)
        assert h1 == h2
        assert len(h1) == 64
        assert all(c in "0123456789abcdef" for c in h1)

    def test_pmtiles_thumbnail_image_hash_includes_prefix(self):
        """Hash incorporates PMTiles prefix to avoid collision with regular image hashes."""
        url = "https://example.com/tiles.pmtiles"
        expected = hashlib.sha256((PMTILES_THUMBNAIL_PREFIX + url).encode()).hexdigest()
        assert _pmtiles_thumbnail_image_hash(url) == expected

    def test_is_pmtiles_url_pmtiles_extension(self):
        """Detect PMTiles URLs by .pmtiles extension."""
        assert _is_pmtiles_url("https://example.com/tiles.pmtiles") is True
        assert _is_pmtiles_url("https://example.com/tiles.PMTILES") is True

    def test_is_pmtiles_url_rejects_non_pmtiles(self):
        """Reject non-PMTiles URLs."""
        assert _is_pmtiles_url("https://example.com/tiles.tif") is False
        assert _is_pmtiles_url("https://example.com/image.jpg") is False
        assert _is_pmtiles_url("") is False


class TestHttpGetBytes:
    """Test _http_get_bytes helper."""

    def test_get_bytes_uses_range_header(self):
        """get_bytes issues Range request (pads small requests to 512 bytes min)."""
        chunk = b"x" * 512  # Small requests are padded to 512 for CDN compatibility
        with patch("app.tasks.worker.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.content = chunk
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            get_bytes = _http_get_bytes("https://example.com/tiles.pmtiles")
            result = get_bytes(0, 127)
            assert result == chunk[:127]  # Returns only requested length
            mock_get.assert_called_once()
            call_kw = mock_get.call_args[1]
            assert call_kw["headers"]["Range"] == "bytes=0-511"  # Min 512 bytes


class TestExtractMvtPoints:
    """Test _extract_mvt_points for bbox calculation."""

    def test_point(self):
        geom = {"type": "Point", "coordinates": [100, 200]}
        assert _extract_mvt_points(geom) == [(100, 200)]

    def test_linestring(self):
        geom = {"type": "LineString", "coordinates": [[0, 0], [100, 100]]}
        assert _extract_mvt_points(geom) == [(0, 0), (100, 100)]

    def test_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]],
        }
        pts = _extract_mvt_points(geom)
        assert len(pts) == 5
        assert pts[0] == (0, 0)
        assert pts[2] == (100, 100)

    def test_multipolygon(self):
        geom = {
            "type": "MultiPolygon",
            "coordinates": [[[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]]],
        }
        pts = _extract_mvt_points(geom)
        assert len(pts) == 5
        assert (10, 10) in pts

    def test_empty_coords_returns_empty(self):
        assert _extract_mvt_points({"type": "Point", "coordinates": []}) == []
        assert _extract_mvt_points({"type": "Polygon", "coordinates": []}) == []
        assert _extract_mvt_points({"type": "Point"}) == []


def _mock_mvt_decode_polygon():
    """Decoded MVT with one polygon (small bbox to test centering/scale)."""
    return {
        "layer": {
            "features": [
                {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [500, 500],
                                [1500, 500],
                                [1500, 1500],
                                [500, 1500],
                                [500, 500],
                            ]
                        ],
                    }
                }
            ]
        }
    }


@pytest.mark.skipif(not MVT_AVAILABLE, reason="mapbox-vector-tile not installed")
class TestRenderMvtToPng:
    """Test _render_mvt_to_png (MVT decode and render)."""

    def test_returns_valid_png_for_polygon(self):
        """Render produces centered, scaled PNG from decoded MVT."""
        mock_decoded = _mock_mvt_decode_polygon()
        with patch("mapbox_vector_tile.decode", return_value=mock_decoded):
            result = _render_mvt_to_png(b"fake-mvt-bytes", 10, 298, 387)
        assert result is not None
        assert result[:8] == b"\x89PNG\r\n\x1a\n"
        img = Image.open(io.BytesIO(result))
        assert img.size == (256, 256)

    def test_returns_none_on_decode_failure(self):
        with patch("mapbox_vector_tile.decode", side_effect=Exception("parse error")):
            result = _render_mvt_to_png(b"bad", 0, 0, 0)
        assert result is None

    def test_returns_none_on_empty_decode(self):
        with patch("mapbox_vector_tile.decode", return_value={}):
            result = _render_mvt_to_png(b"empty", 0, 0, 0)
        assert result is None

    def test_returns_none_when_no_geometry_points(self):
        with patch("mapbox_vector_tile.decode", return_value={"layer": {"features": []}}):
            result = _render_mvt_to_png(b"no-features", 0, 0, 0)
        assert result is None


@pytest.mark.skipif(not PMTILES_AVAILABLE, reason="pmtiles not installed")
class TestGeneratePmtilesThumbnailBytes:
    """Test _generate_pmtiles_thumbnail_bytes."""

    def test_returns_none_when_mvt_tile_empty(self):
        """Returns None when MVT tile has no data (reader.get returns empty)."""
        mock_header = {
            "tile_type": MagicMock(value=1),  # MVT
            "min_zoom": 0,
            "max_zoom": 14,
            "tile_compression": MagicMock(value=1),  # NONE
        }
        mock_reader = MagicMock()
        mock_reader.header.return_value = mock_header
        mock_reader.get.return_value = b""  # No tile data

        def fake_get_bytes(_url):
            return lambda _o, _l: b"x" * 512  # Enough for PMTiles header parse

        with (
            patch("app.tasks.worker._http_get_bytes", return_value=fake_get_bytes),
            patch("pmtiles.reader.Reader", return_value=mock_reader),
        ):
            result = _generate_pmtiles_thumbnail_bytes("https://example.com/vector.pmtiles")
            assert result is None

    def test_returns_none_on_http_failure(self):
        """Returns None when HTTP range request fails."""

        def raise_err(*_args, **_kw):
            raise Exception("Connection refused")

        with patch("app.tasks.worker._http_get_bytes", return_value=raise_err):
            result = _generate_pmtiles_thumbnail_bytes("https://example.com/tiles.pmtiles")
            assert result is None

    def test_returns_tile_bytes_on_raster_success(self):
        """Returns tile bytes for raster PMTiles when tile is found."""
        png_bytes = _valid_png_bytes()
        mock_header = {
            "tile_type": MagicMock(value=2),  # PNG
            "min_zoom": 0,
            "max_zoom": 14,
        }
        mock_reader = MagicMock()
        mock_reader.header.return_value = mock_header
        mock_reader.get.return_value = png_bytes

        def fake_get_bytes(_url):
            return lambda _o, _l: b"x" * 512

        with (
            patch("app.tasks.worker._http_get_bytes", return_value=fake_get_bytes),
            patch("pmtiles.reader.Reader", return_value=mock_reader),
        ):
            result = _generate_pmtiles_thumbnail_bytes("https://example.com/raster.pmtiles")
            assert result == png_bytes

    def test_returns_png_on_mvt_success(self):
        """Returns PNG when MVT tile is found and renders successfully."""
        mock_decoded = _mock_mvt_decode_polygon()
        mock_header = {
            "tile_type": MagicMock(value=1),  # MVT
            "min_zoom": 5,
            "max_zoom": 12,
            "min_lon_e7": int(-75.2 * 1e7),
            "min_lat_e7": int(39.8 * 1e7),
            "max_lon_e7": int(-74.9 * 1e7),
            "max_lat_e7": int(40.2 * 1e7),
            "tile_compression": MagicMock(value=1),  # NONE
        }
        mock_reader = MagicMock()
        mock_reader.header.return_value = mock_header
        mock_reader.get.return_value = b"fake-mvt-bytes"  # >= 10 bytes, raw MVT (no gzip)

        def fake_get_bytes(_url):
            return lambda _o, _l: b"x" * 512

        with (
            patch("app.tasks.worker._http_get_bytes", return_value=fake_get_bytes),
            patch("pmtiles.reader.Reader", return_value=mock_reader),
            patch("mapbox_vector_tile.decode", return_value=mock_decoded),
        ):
            result = _generate_pmtiles_thumbnail_bytes("https://example.com/vector.pmtiles")
            assert result is not None
            assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_mvt_gzip_decompression(self):
        """MVT tiles with tile_compression=GZIP are decompressed before decode."""
        mock_decoded = _mock_mvt_decode_polygon()
        gzipped_mvt = gzip.compress(b"inner-mvt-bytes")
        mock_header = {
            "tile_type": MagicMock(value=1),
            "min_zoom": 5,
            "max_zoom": 12,
            "min_lon_e7": int(-75.2 * 1e7),
            "min_lat_e7": int(39.8 * 1e7),
            "max_lon_e7": int(-74.9 * 1e7),
            "max_lat_e7": int(40.2 * 1e7),
            "tile_compression": MagicMock(value=2),  # GZIP
        }
        mock_reader = MagicMock()
        mock_reader.header.return_value = mock_header
        mock_reader.get.return_value = gzipped_mvt

        def fake_get_bytes(_url):
            return lambda _o, _l: b"x" * 512

        with (
            patch("app.tasks.worker._http_get_bytes", return_value=fake_get_bytes),
            patch("pmtiles.reader.Reader", return_value=mock_reader),
            patch("mapbox_vector_tile.decode", return_value=mock_decoded) as mock_decode,
        ):
            result = _generate_pmtiles_thumbnail_bytes("https://example.com/vector.pmtiles")
            assert result is not None
            # decode should have been called with decompressed bytes
            mock_decode.assert_called_once()
            call_args = mock_decode.call_args[0][0]
            assert call_args == b"inner-mvt-bytes"


# Known-good raster PMTiles URL (pmtiles.io demo; Stamen Toner, CC-BY-ODbL).
# Use this to verify the harvest pipeline works. The fixture b1g_PJxxfKgpqpUT uses
# MVT PMTiles which may have no tiles at the coordinates we request or MVT decode
# issues—raster is the reliable path.
_STAMEN_RASTER_PMTILES = "https://pmtiles.io/stamen_toner(raster)CC-BY+ODbL_z3.pmtiles"


@pytest.mark.skipif(not PMTILES_AVAILABLE, reason="pmtiles not installed")
@pytest.mark.network
@pytest.mark.slow
class TestPmtilesThumbnailRealNetwork:
    """
    Integration tests that fetch real PMTiles from the internet.

    Run with: pytest -m network tests/tasks/test_worker_pmtiles_thumbnail.py
    These prove we can harvest thumbnails from PMTiles; unit tests use mocks.
    """

    def test_raster_pmtiles_produces_valid_png(self):
        """
        Fetch a real raster PMTiles and assert we get valid PNG bytes.

        This is the proof that PMTiles thumbnail harvest works. The fixture
        b1g_PJxxfKgpqpUT fails because it uses MVT tiles (sparse or decode issues).
        """
        result = _generate_pmtiles_thumbnail_bytes(_STAMEN_RASTER_PMTILES)
        assert result is not None, "Expected PNG bytes from Stamen raster PMTiles"
        assert len(result) >= 100, "Expected meaningful PNG (>100 bytes)"
        # Verify PNG signature
        assert result[:8] == b"\x89PNG\r\n\x1a\n", "Expected PNG magic bytes"
        # Basic sanity: load with PIL
        img = Image.open(io.BytesIO(result))
        assert img.size[0] > 0 and img.size[1] > 0


class TestGeneratePmtilesThumbnailTask:
    """Test generate_pmtiles_thumbnail Celery task."""

    def test_returns_true_when_already_cached(self):
        """Returns True immediately when image is already in Redis."""
        pmtiles_url = "https://example.com/tiles.pmtiles"
        image_hash = _pmtiles_thumbnail_image_hash(pmtiles_url)
        image_key = f"image:{image_hash}"

        with patch("app.tasks.worker.redis_client") as mock_redis:
            mock_redis.exists.return_value = True
            result = generate_pmtiles_thumbnail(pmtiles_url)
            assert result is True
            mock_redis.exists.assert_called_with(image_key)

    def test_returns_true_and_caches_on_success(self):
        """Returns True and caches image when generation succeeds."""
        pmtiles_url = "https://example.com/tiles.pmtiles"
        png_bytes = _valid_png_bytes()

        with (
            patch("app.tasks.worker.redis_client") as mock_redis,
            patch(
                "app.tasks.worker._generate_pmtiles_thumbnail_bytes",
                return_value=png_bytes,
            ),
        ):
            mock_redis.exists.return_value = False
            result = generate_pmtiles_thumbnail(pmtiles_url)
            assert result is True
            mock_redis.setex.assert_called()
            calls = [c[0][0] for c in mock_redis.setex.call_args_list]
            assert any("image:" in k for k in calls)

    def test_returns_false_when_generation_fails(self):
        """Returns False when _generate_pmtiles_thumbnail_bytes returns None."""
        pmtiles_url = "https://example.com/vector.pmtiles"

        with (
            patch("app.tasks.worker.redis_client") as mock_redis,
            patch(
                "app.tasks.worker._generate_pmtiles_thumbnail_bytes",
                return_value=None,
            ),
        ):
            mock_redis.exists.return_value = False
            result = generate_pmtiles_thumbnail(pmtiles_url)
            assert result is False
            # Should cache skip marker (pmtiles_skip_v2:...), not an image
            setex_calls = mock_redis.setex.call_args_list
            assert all("pmtiles_skip_v2:" in str(c[0][0]) for c in setex_calls)
