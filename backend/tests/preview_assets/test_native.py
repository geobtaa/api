import io
import json
import re
from contextlib import contextmanager

import numpy as np
import pytest
import rasterio
from rasterio.enums import ColorInterp
from rasterio.shutil import copy as raster_copy
from rasterio.transform import from_origin

from app.services.preview_assets import io as source_io
from app.services.preview_assets.io import Budget, RangeReader
from app.services.preview_assets.models import Limits, Outcome, PreviewError
from app.services.preview_assets.native import inspect_cog, inspect_pmtiles


def remote(
    monkeypatch, content, *, etag='"version-one"', status=206, change=False, malformed=False
):
    calls = []

    @contextmanager
    def request(url, budget, host_guard=None, headers=None):
        lo, hi = map(int, re.search(r"bytes=(\d+)-(\d+)", headers["Range"]).groups())
        hi = min(hi, len(content) - 1)
        calls.append((lo, hi, headers))

        class Response:
            headers = {"Content-Range": f"bytes {lo}-{hi}/{len(content)}", "ETag": etag}

            def stream(self, size, decode_content=False):
                data = content[lo : hi + 1]
                for offset in range(0, len(data), size):
                    yield data[offset : offset + size]

        response = Response()
        response.status = status
        if change and len(calls) > 1:
            response.headers["ETag"] = '"new-version"'
        if malformed:
            response.headers["Content-Range"] = "bytes 4-8/9"
        yield response, url

    monkeypatch.setattr(source_io, "source_response", request)
    return calls


def test_range_reader_bounded_cache_and_validator(monkeypatch, tmp_path):
    content = bytes(range(256)) * 4096
    calls = remote(monkeypatch, content)
    budget = Budget(Limits(download_bytes=3 * RangeReader.BLOCK), tmp_path)
    with RangeReader("https://example.org/source", budget) as stream:
        assert stream.read_at(2, 40) == content[2:42]
        assert stream.read_at(len(content) - 40, 40) == content[-40:]
        assert stream.read_at(2, 40) == content[2:42]
        assert stream.read_at(len(content) + 5, 10) == b""
        assert len(calls) == 2
        assert calls[1][2]["If-Match"] == '"version-one"'
        assert budget.bytes_read == 2 * RangeReader.BLOCK < len(content)
        assert stream.fingerprint


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"status": 200}, Outcome.UNSUPPORTED),
        ({"etag": 'W/"weak"'}, Outcome.UNSUPPORTED),
        ({"malformed": True}, Outcome.INVALID),
        ({"change": True}, Outcome.INVALID),
    ],
)
def test_range_reader_rejects_unreliable_representations(monkeypatch, tmp_path, kwargs, expected):
    remote(monkeypatch, b"x" * 200000, **kwargs)
    with pytest.raises(PreviewError) as error:
        stream = RangeReader("https://example.org/data", Budget(Limits(), tmp_path))
        stream.read_at(100000, 20)
    assert error.value.status == expected


def test_range_reader_counts_all_downloads(monkeypatch, tmp_path):
    remote(monkeypatch, b"x" * 200000)
    budget = Budget(Limits(download_bytes=70000), tmp_path)
    stream = RangeReader("https://example.org/data", budget)
    with pytest.raises(PreviewError, match="Download limit"):
        stream.read_at(100000, 20)
    assert budget.bytes_read == RangeReader.BLOCK


def test_native_cog_reads_overview_not_full_resolution(monkeypatch, tmp_path):
    source, cog = tmp_path / "source.tif", tmp_path / "cloud.tif"
    rng = np.random.default_rng(17)
    with rasterio.open(
        source,
        "w",
        driver="GTiff",
        width=2048,
        height=2048,
        count=3,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(-92, 45, 0.001, 0.001),
    ) as dataset:
        dataset.write(rng.integers(0, 256, (3, 2048, 2048), dtype=np.uint8))
        dataset.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
    raster_copy(source, cog, driver="COG", compress="LZW", blocksize=256)
    calls = remote(monkeypatch, cog.read_bytes())
    budget = Budget(Limits(), tmp_path)
    with RangeReader("https://example.org/source.tif", budget) as stream:
        layers, coverage, status = inspect_cog(stream, tmp_path / "thumb.png")
        assert stream.fingerprint
    assert status == Outcome.READY
    assert layers[0].recipe.bands == [1, 2, 3]
    assert layers[0].bounds == pytest.approx([-92, 42.952, -89.952, 45])
    assert coverage.kind == "data-footprint"
    assert budget.bytes_read < cog.stat().st_size / 5
    assert len(calls) > 1


def test_native_pmtiles_renders_real_features_and_exposes_layers(monkeypatch, tmp_path):
    import gzip

    import mapbox_vector_tile
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    from pmtiles.writer import Writer

    content = io.BytesIO()
    tile = mapbox_vector_tile.encode(
        [
            {
                "name": name,
                "features": [
                    {
                        "geometry": "POLYGON ((10 10, 4000 10, 2000 4000, 10 10))",
                        "properties": {"label": name},
                        "id": 14,
                    }
                ],
            }
            for name in ("parks", "lakes")
        ]
    )
    writer = Writer(content)
    writer.write_tile(zxy_to_tileid(0, 0, 0), gzip.compress(tile))
    writer.finalize(
        {
            "tile_type": TileType.MVT,
            "tile_compression": Compression.GZIP,
            "min_lon_e7": -1800000000,
            "max_lon_e7": 1800000000,
            "min_lat_e7": -850000000,
            "max_lat_e7": 850000000,
        },
        {"vector_layers": [{"id": "parks"}, {"id": "lakes"}]},
    )
    remote(monkeypatch, content.getvalue())
    budget = Budget(Limits(), tmp_path)
    with RangeReader("https://example.org/map.pmtiles", budget) as stream:
        layers, coverage, status = inspect_pmtiles(stream, tmp_path / "thumb.png", budget)
    assert [layer.name for layer in layers] == ["parks", "lakes"]
    assert status == Outcome.READY
    features = json.loads((tmp_path / "thumb.geojson").read_text())["features"]
    assert {f["properties"]["label"] for f in features} == {"parks", "lakes"}
    assert coverage.label == "Data extent"
