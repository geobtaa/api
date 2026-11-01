import numpy as np
from PIL import Image

from app.services.preview_assets.image_encoding import optimize_png


def test_palette_reduces_graphics_without_changing_colors(tmp_path):
    path = tmp_path / "graphic.png"
    pixels = np.zeros((256, 256, 3), dtype=np.uint8)
    pixels[:128] = [20, 80, 160]
    pixels[128:] = [250, 250, 250]
    Image.fromarray(pixels).save(path)
    before = path.stat().st_size
    optimize_png(path)
    with Image.open(path) as image:
        assert image.mode == "P"
        np.testing.assert_array_equal(np.asarray(image.convert("RGB")), pixels)
    assert path.stat().st_size < before


def test_palette_preserves_alpha_and_bounds_color_error(tmp_path):
    path = tmp_path / "alpha.png"
    rng = np.random.default_rng(42)
    pixels = rng.integers(0, 256, (64, 64, 4), dtype=np.uint8)
    Image.fromarray(pixels).save(path)
    optimize_png(path)
    with Image.open(path) as image:
        actual = np.asarray(image.convert("RGBA"))
    np.testing.assert_array_equal(actual[:, :, 3], pixels[:, :, 3])
    delta = actual[:, :, :3].astype(float) - pixels[:, :, :3]
    assert np.sqrt(np.mean(delta**2)) <= 3
    assert np.abs(delta).max() <= 48
