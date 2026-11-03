"""Inspect existing cloud-optimized assets through controlled partial reads."""

import gzip
import io
import json
import math

import mapbox_vector_tile
import mercantile
import rasterio
from pmtiles.reader import Reader
from pmtiles.tile import Compression, TileType
from rasterio.warp import transform_bounds
from shapely.geometry import mapping

from .convert import raster_recipe
from .geometry import bounds_geometry
from .models import Coverage, Layer, Outcome, PreviewError, Recipe
from .render import render_raster, render_vector


class RangeHandle(io.RawIOBase):
    """A separate cursor whose close does not dispose the shared range cache."""

    def __init__(self, stream):
        self.stream, self.position = stream, 0

    def read(self, size=-1):
        result = self.stream.read_at(self.position, size)
        self.position += len(result)
        return result

    def seek(self, offset, whence=0):
        position = offset + (
            self.position if whence == 1 else self.stream.size if whence == 2 else 0
        )
        if whence not in {0, 1, 2} or position < 0:
            raise ValueError("Invalid source seek")
        self.position = position
        return position

    def tell(self):
        return self.position

    def readable(self):
        return True

    def seekable(self):
        return True


def inspect_cog(stream, thumbnail, supplied=None):
    try:
        return _inspect_cog(stream, thumbnail, supplied)
    except Exception:
        if getattr(stream, "failure", None):
            raise stream.failure from None
        raise


def _inspect_cog(stream, thumbnail, supplied=None):
    # Only this exact virtual file can be opened. No sibling/sidecar lookup may
    # cause GDAL to escape controlled retrieval or read a worker-local file.
    def opener(path, mode="rb"):
        if path != "source.tif" or mode not in {"r", "rb"}:
            raise FileNotFoundError(path)
        return RangeHandle(stream)

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_PAM_ENABLED="NO"):
        with rasterio.open("source.tif", opener=opener, driver="GTiff") as src:
            if src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") != "COG":
                raise PreviewError(Outcome.UNSUPPORTED, "Source needs COG conversion")
            if not src.crs:
                raise PreviewError(Outcome.NEEDS_REVIEW, "Raster CRS missing")
            recipe = raster_recipe(src, supplied)
            bounds = list(transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21))
            coverage = Coverage(
                geometry=mapping(bounds_geometry(bounds)),
                kind="data-footprint",
                label="Data footprint",
                provenance="Georeferenced source COG grid bounds (includes NoData areas)",
            )
            status = render_raster(src, recipe, thumbnail)
    return (
        [
            Layer(
                id="native",
                name="Source COG",
                url=stream.url,
                format="cog",
                bounds=bounds,
                recipe=recipe,
            )
        ],
        coverage,
        status,
    )


def inspect_pmtiles(stream, thumbnail, budget, supplied=None, selected_layer=None):
    if stream.read_at(0, 8) != b"PMTiles\x03":
        raise PreviewError(Outcome.UNSUPPORTED, "Requires a PMTiles version 3 archive")

    def bounded_read(offset, length):
        if offset < 0 or length < 0 or offset + length > stream.size:
            raise PreviewError(Outcome.INVALID, "PMTiles entry exceeds source bounds")
        if length > 16 * 1024 * 1024:
            raise PreviewError(Outcome.OVER_LIMIT, "PMTiles entry size limit exceeded")
        data = stream.read_at(offset, length)
        if data.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                expanded = compressed.read(16 * 1024 * 1024 + 1)
            if len(expanded) > 16 * 1024 * 1024:
                raise PreviewError(Outcome.OVER_LIMIT, "PMTiles entry expansion limit exceeded")
        return data

    reader = Reader(bounded_read)
    header, metadata = reader.header(), reader.metadata()
    if header["internal_compression"] != Compression.GZIP:
        raise PreviewError(Outcome.UNSUPPORTED, "PMTiles directory compression is unsupported")
    if not 0 <= header["min_zoom"] <= header["max_zoom"] <= 26:
        raise PreviewError(Outcome.INVALID, "Invalid PMTiles zoom range")
    if header["tile_type"] != TileType.MVT:
        raise PreviewError(Outcome.UNSUPPORTED, "Only vector PMTiles inspection is supported")
    if header["addressed_tiles_count"] < 1:
        raise PreviewError(Outcome.INVALID, "Empty PMTiles archive")
    if header["tile_compression"] not in {Compression.NONE, Compression.GZIP}:
        raise PreviewError(Outcome.UNSUPPORTED, "Unsupported vector tile compression")
    names = [item["id"] for item in metadata.get("vector_layers", [])]
    if not names or len(names) != len(set(names)):
        raise PreviewError(Outcome.NEEDS_REVIEW, "PMTiles layer identity missing or ambiguous")
    if selected_layer:
        if selected_layer not in names:
            raise PreviewError(Outcome.NEEDS_REVIEW, "Selected layer not found")
        names = [selected_layer]
    if len(names) > budget.limits.layers:
        raise PreviewError(Outcome.OVER_LIMIT, "PMTiles spatial layer limit exceeded")
    bounds = [header[f"{axis}_e7"] / 1e7 for axis in ("min_lon", "min_lat", "max_lon", "max_lat")]
    coverage = Coverage(
        geometry=mapping(bounds_geometry(bounds)),
        kind="data-footprint",
        label="Data extent",
        provenance="Source PMTiles archive bounds; gaps may be included",
    )
    recipe = supplied or Recipe(kind="vector")
    if recipe.kind != "vector":
        raise PreviewError(Outcome.NEEDS_REVIEW, "Vector layer requires a vector recipe")
    layers = [
        Layer(
            id=name,
            name=name,
            url=stream.url,
            format="pmtiles",
            recipe=recipe,
            bounds=bounds,
            source_layer=name,
        )
        for name in names
    ]
    # Choose one complete overview level with at most 64 tiles. The thumbnail
    # represents the archive's generalized overview, never a fabricated shape.
    tiles = []
    for zoom in range(header["min_zoom"], min(header["max_zoom"], 12) + 1):
        candidate = []
        for tile in mercantile.tiles(*bounds, zooms=zoom):
            candidate.append(tile)
            if len(candidate) > 64:
                break
        if len(candidate) > 64:
            break
        tiles = candidate
    if not tiles:
        return layers, coverage, Outcome.NEEDS_REVIEW
    sequence = thumbnail.with_suffix(".geojson")
    features = []
    for tile in tiles:
        budget.check()
        data = reader.get(tile.z, tile.x, tile.y)
        if not data:
            continue
        if header["tile_compression"] == Compression.GZIP:
            # Bound decompressed tile size before handing it to the decoder.
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                data = compressed.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise PreviewError(Outcome.OVER_LIMIT, "Vector tile expansion limit exceeded")
        decoded = mapbox_vector_tile.decode(data)
        for name in names:
            layer = decoded.get(name)
            if not layer:
                continue
            extent = layer["extent"]

            def geographic(coords, tile=tile, extent=extent):
                if not isinstance(coords[0], (int, float)):
                    return [geographic(item) for item in coords]
                x, y = coords[:2]
                longitude = (tile.x + x / extent) / 2**tile.z * 360 - 180
                latitude = math.degrees(
                    math.atan(math.sinh(math.pi * (1 - 2 * (tile.y + 1 - y / extent) / 2**tile.z)))
                )
                return [longitude, latitude]

            for feature in layer["features"]:
                value = feature["geometry"]
                value["coordinates"] = geographic(value["coordinates"])
                features.append(feature)
                if len(features) > 100000:
                    raise PreviewError(Outcome.OVER_LIMIT, "Overview feature limit exceeded")
    if not features:
        return layers, coverage, Outcome.NEEDS_REVIEW
    sequence.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    budget.check()
    return layers, coverage, render_vector(sequence, recipe, bounds, thumbnail, budget)
