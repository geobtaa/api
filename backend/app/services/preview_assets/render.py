"""Render actual content using the same versioned recipe exposed to the viewer."""

import math
from pathlib import Path

import fiona
import numpy as np
import rasterio
from PIL import Image, ImageColor, ImageDraw
from rasterio.enums import Resampling
from rio_tiler.colormap import cmap

from .models import Outcome, PreviewError


def render_raster(path: Path, recipe, target: Path):
    with rasterio.open(path) as src:
        scale = min(512 / src.width, 512 / src.height, 1)
        height, width = max(1, round(src.height * scale)), max(1, round(src.width * scale))
        values = src.read(
            recipe.bands,
            out_shape=(len(recipe.bands), height, width),
            masked=True,
            resampling=Resampling.nearest if recipe.kind == "classified" else Resampling.average,
        )
        valid = ~np.any(np.ma.getmaskarray(values), axis=0) & np.all(
            np.isfinite(values.data), axis=0
        )
        if recipe.nodata is not None:
            valid &= ~np.any(values.data == recipe.nodata, axis=0)
        output = np.zeros((height, width, 4), dtype=np.uint8)
        if recipe.kind == "classified":
            for code, rgba in recipe.palette.items():
                output[values.data[0] == code] = rgba
        elif recipe.kind == "scalar":
            if recipe.value_range is None:
                raise PreviewError(Outcome.NEEDS_REVIEW, "Scalar recipe requires a value range")
            lo, hi = recipe.value_range
            indices = np.clip(
                np.nan_to_num((values.data[0] - lo) / (hi - lo), nan=0) * 255, 0, 255
            ).astype(np.uint8)
            palette = recipe.palette or cmap.get(recipe.ramp)
            lookup = np.array([palette[i] for i in range(256)], dtype=np.uint8)
            output[:] = lookup[indices]
        else:
            data = values.data
            if recipe.value_range:
                lo, hi = recipe.value_range
                data = (data.astype(float) - lo) / (hi - lo) * 255
            output[:, :, :3] = np.moveaxis(np.clip(data, 0, 255).astype(np.uint8), 0, -1)
            output[:, :, 3] = 255
        output[~valid, 3] = 0
        Image.fromarray(output).save(target, optimize=True)
    return quality(target)


def render_vector(sequence: Path, recipe, bounds, target: Path, budget):
    image = Image.new("RGB", (512, 512), "#f5f7fa")
    draw = ImageDraw.Draw(image)
    west, south, east, north = bounds

    # Project to Web Mercator to match the viewer's default flat-map framing.
    def mercator(lat):
        return math.log(math.tan(math.pi / 4 + math.radians(max(-85.0511, min(85.0511, lat))) / 2))

    xmin, xmax = math.radians(west), math.radians(east)
    ymin, ymax = mercator(south), mercator(north)
    scale = min(480 / max(xmax - xmin, 1e-9), 480 / max(ymax - ymin, 1e-9))

    def point(coordinate):
        return (
            256 + (math.radians(coordinate[0]) - (xmin + xmax) / 2) * scale,
            256 - (mercator(coordinate[1]) - (ymin + ymax) / 2) * scale,
        )

    def geometry(value):
        kind, coords = value["type"], value.get("coordinates")
        if kind == "GeometryCollection":
            for child in value["geometries"]:
                geometry(child)
        elif kind.startswith("Multi"):
            for child in coords:
                geometry({"type": kind[5:], "coordinates": child})
        elif kind == "Point":
            x, y = point(coords)
            r = recipe.point_radius
            draw.ellipse((x - r, y - r, x + r, y + r), fill=recipe.color)
        elif kind == "LineString" and len(coords) > 1:
            draw.line(
                [point(c) for c in coords], fill=recipe.color, width=round(recipe.stroke_width)
            )
        elif kind == "Polygon":
            # Draw holes on an individual transparent layer so they do not erase
            # other features underneath.
            overlay = Image.new("RGBA", image.size)
            painter = ImageDraw.Draw(overlay)
            for i, ring in enumerate(coords):
                if len(ring) >= 3:
                    painter.polygon(
                        [point(c) for c in ring],
                        fill=(*ImageColor.getrgb(recipe.color), round(255 * recipe.fill_opacity))
                        if i == 0
                        else (0, 0, 0, 0),
                    )
            for ring in coords:
                if len(ring) >= 3:
                    painter.line(
                        [point(c) for c in ring],
                        fill=recipe.color,
                        width=max(1, round(recipe.stroke_width)),
                    )
            image.paste(overlay, mask=overlay.getchannel("A"))

    with fiona.open(sequence) as source:
        for i, feature in enumerate(source):
            if i % 1000 == 0:
                budget.check()
            if feature.get("geometry"):
                geometry(feature["geometry"])
    image.save(target, optimize=True)
    return quality(target)


def quality(path: Path):
    with Image.open(path) as image:
        image.thumbnail((512, 512))
        image.save(path, optimize=True)
        rgba = np.asarray(image.convert("RGBA"))
        pixels = rgba[:, :, :3][rgba[:, :, 3] > 0]
    if path.stat().st_size > 512 * 1024:
        # Bound the thumbnail size with palette quantization.
        with Image.open(path) as image:
            image.convert("RGBA").quantize(colors=256).save(path, optimize=True)
    if path.stat().st_size > 512 * 1024:
        raise PreviewError(Outcome.OVER_LIMIT, "Thumbnail exceeds 512 KB")
    if (
        not pixels.size
        or float(np.std(pixels.astype(float), axis=0).max()) < 1
        or float(np.percentile(pixels, 99)) < 20
    ):
        return Outcome.NEEDS_REVIEW
    _, counts = np.unique(pixels, axis=0, return_counts=True)
    if float(counts.max()) / len(pixels) > 0.999:
        return Outcome.NEEDS_REVIEW
    return Outcome.READY
