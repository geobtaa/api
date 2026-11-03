"""Small display images with bounded palette error; never used for data rasters."""

from io import BytesIO

import numpy as np
from PIL import Image

ENCODING_VERSION = "display-encoding-1"


def optimize_png(path):
    """Choose the smallest verified candidate, preserving alpha and fine colors.

    PNG palettes are exact for simple graphics. For continuous-tone images allow
    at most three intensity levels RMS and 48 levels maximum RGB error. Keep
    the truecolor file if a palette cannot meet that bound. No dithering adds
    noise around map lettering. Dimensions never change here.
    """
    with Image.open(path) as source:
        image = source.convert("RGBA")
    reference = np.asarray(image)
    output = BytesIO()
    image.save(output, "PNG", optimize=True, compress_level=9)
    best = output.getvalue()
    opaque = bool(np.all(reference[:, :, 3] == 255))
    rgb = image.convert("RGB") if opaque else image
    for colors in (64, 128, 256):
        candidate = rgb.quantize(
            colors=colors,
            method=Image.Quantize.MEDIANCUT if opaque else Image.Quantize.FASTOCTREE,
            dither=Image.Dither.NONE,
        )
        decoded = np.asarray(candidate.convert("RGBA"))
        if not np.array_equal(reference[:, :, 3], decoded[:, :, 3]):
            continue
        difference = reference[:, :, :3].astype(np.float32) - decoded[:, :, :3]
        visible = reference[:, :, 3] > 0
        difference = difference[visible]
        if difference.size and (
            np.sqrt(np.mean(difference**2)) > 3 or np.max(np.abs(difference)) > 48
        ):
            continue
        stream = BytesIO()
        candidate.save(stream, "PNG", optimize=True, compress_level=9)
        if stream.tell() < len(best):
            best = stream.getvalue()
    with Image.open(BytesIO(best)) as check:
        check.verify()
    path.write_bytes(best)
