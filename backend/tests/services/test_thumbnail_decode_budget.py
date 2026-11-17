"""Exercise decoder-level thumbnail reduction with real encoded images."""

import io

import pytest
from PIL import Image, Jpeg2KImagePlugin, features

from app.services import thumbnail_policy as policy


@pytest.mark.skipif(not features.check("jpg_2000"), reason="OpenJPEG is unavailable")
def test_mislabeled_jpeg2000_is_reduced_before_decoding(monkeypatch):
    source = io.BytesIO()
    Image.new("RGB", (3072, 2048), (40, 100, 180)).save(source, format="JPEG2000")
    original_load = Jpeg2KImagePlugin.Jpeg2KImageFile.load
    decoded = []

    def record_load(image):
        if image.tile:
            decoded.append((image.size, image.reduce))
        return original_load(image)

    monkeypatch.setattr(Jpeg2KImagePlugin.Jpeg2KImageFile, "load", record_load)
    body, mime = policy.normalize_thumbnail_image(source.getvalue(), "image/jpeg")

    assert decoded == [((3072, 2048), 2)]
    assert mime == "image/jpeg"
    assert body and len(body) <= policy.THUMBNAIL_MAX_BYTES
    with Image.open(io.BytesIO(body)) as result:
        assert result.size == (512, 341)
        assert result.format == "JPEG"
        result.load()
        assert all(abs(a - b) <= 3 for a, b in zip(result.getpixel((0, 0)), (40, 100, 180)))


@pytest.mark.skipif(not features.check("jpg_2000"), reason="OpenJPEG is unavailable")
@pytest.mark.parametrize("size", [(200, 100), (1200, 800)])
def test_small_jpeg2000_does_not_require_extra_resolution_levels(size):
    source = io.BytesIO()
    Image.new("RGB", size, (40, 100, 180)).save(source, format="JPEG2000", num_resolutions=1)
    body, mime = policy.normalize_thumbnail_image(source.getvalue(), "image/jp2")
    assert body and mime == "image/jpeg"
    with Image.open(io.BytesIO(body)) as result:
        assert result.size == ((200, 100) if size == (200, 100) else (512, 341))


@pytest.mark.skipif(not features.check("jpg_2000"), reason="OpenJPEG is unavailable")
def test_unavailable_reduced_resolution_does_not_retry_full_decode():
    source = io.BytesIO()
    Image.new("RGB", (2048, 2048)).save(source, format="JPEG2000", num_resolutions=1)
    assert policy.normalize_thumbnail_image(source.getvalue(), "image/jp2") == (None, None)


@pytest.mark.parametrize("edge", [0, -1])
def test_nonpositive_output_edge_is_rejected_before_decoding(monkeypatch, edge):
    source = io.BytesIO()
    Image.new("RGB", (20, 10)).save(source, format="PNG")
    monkeypatch.setattr(policy, "THUMBNAIL_MAX_EDGE", edge)
    monkeypatch.setattr(
        policy.Image, "open", lambda *args: pytest.fail("Invalid bounds must not decode")
    )
    assert policy.normalize_thumbnail_image(source.getvalue(), "image/png") == (None, None)
