"""Coverage-only static maps with regional panels for disconnected footprints."""

import io

import requests
from PIL import Image, ImageDraw
from shapely import affinity
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from app.services.native_static_maps import renderer_url


def panels(geometry):
    geom = shape(geometry)
    parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    # Keep dateline neighbors together in the renderer's unwrapped world.
    if geom.bounds[2] - geom.bounds[0] > 180 and all(
        p.bounds[2] - p.bounds[0] < 180 for p in parts
    ):
        shifted = [affinity.translate(p, xoff=360) if p.centroid.x < 0 else p for p in parts]
        joined = unary_union(shifted)
        if joined.bounds[2] - joined.bounds[0] < geom.bounds[2] - geom.bounds[0]:
            parts, geom = shifted, joined
    if len(parts) > 1 and geom.area and geom.envelope.area > 2 * geom.area:
        ordered = sorted(parts, key=lambda p: (-p.area, p.bounds))
        # All geometry remains represented, including small remote islands.
        return ordered[:3] + [unary_union(ordered[3:])] if len(ordered) > 4 else ordered
    return [geom]


def render_coverage(coverage, target, budget):
    if not coverage.geometry:
        return False
    regions = panels(coverage.geometry)
    canvas = Image.new("RGB", (800, 600), "#f5f7fa")
    columns = 1 if len(regions) == 1 else 2
    rows = (len(regions) + columns - 1) // columns
    width, height = 800 // columns, 560 // rows
    for i, geometry in enumerate(regions):
        budget.check()
        bounds = list(geometry.bounds)
        if bounds[2] == bounds[0]:
            bounds[0], bounds[2] = bounds[0] - 0.01, bounds[2] + 0.01
        if bounds[3] == bounds[1]:
            bounds[1], bounds[3] = bounds[1] - 0.01, bounds[3] + 0.01
        spec = {
            "width": width,
            "height": height,
            "bounds": bounds,
            "geometry": mapping(geometry),
        }
        response = requests.post(
            renderer_url() + "/render", json=spec, timeout=(5, min(60, budget.limits.seconds))
        )
        response.raise_for_status()
        with Image.open(io.BytesIO(response.content)) as image:
            if image.size != (width, height):
                raise ValueError("Coverage renderer returned unexpected dimensions")
            canvas.paste(image.convert("RGB"), ((i % columns) * width, (i // columns) * height))
    label = coverage.label + (" - regional views at different scales" if len(regions) > 1 else "")
    ImageDraw.Draw(canvas).text((14, 575), label, fill="#334155")
    canvas.save(target, optimize=True)
    return True
