"""Prepare local, validated inputs as COG and vector PMTiles derivatives."""

import math
from pathlib import Path

import fiona
import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.warp import transform_bounds
from rio_tiler.colormap import cmap
from shapely.geometry import mapping

from .geometry import bounds_geometry
from .io import extract_zip
from .models import Coverage, Outcome, PreviewError, Recipe
from .process import run_tool

GDAL_VERSION = "3.11.0"
TIPPECANOE_VERSION = "2.79.0"


def verify_tools(budget, vector=False):
    version = run_tool(["gdalinfo", "--version"], budget)
    if not version.startswith(f"GDAL {GDAL_VERSION}"):
        raise PreviewError(Outcome.UNSUPPORTED, f"Requires GDAL {GDAL_VERSION}")
    if vector and f"v{TIPPECANOE_VERSION}" not in run_tool(["tippecanoe", "--version"], budget):
        raise PreviewError(Outcome.UNSUPPORTED, f"Requires Tippecanoe {TIPPECANOE_VERSION}")


def raster_recipe(src, supplied: Recipe | None) -> Recipe:
    if supplied:
        if max(supplied.bands) > src.count or supplied.kind == "vector":
            raise PreviewError(Outcome.NEEDS_REVIEW, "Recipe does not match raster bands")
        if supplied.kind == "scalar" and not supplied.value_range:
            raise PreviewError(Outcome.NEEDS_REVIEW, "Scalar recipe requires an explicit range")
        if supplied.kind == "scalar" and not supplied.palette:
            supplied = supplied.model_copy(update={"palette": cmap.get(supplied.ramp)})
        return supplied
    if src.count >= 3 and all(
        c in src.colorinterp for c in (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
    ):
        if any(dtype != "uint8" for dtype in src.dtypes):
            raise PreviewError(Outcome.NEEDS_REVIEW, "Non-byte imagery needs an explicit stretch")
        return Recipe(
            kind="rgb",
            bands=[
                src.colorinterp.index(c) + 1
                for c in (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
            ],
        )
    try:
        palette = src.colormap(1)
    except ValueError:
        palette = None
    if src.count == 1 and palette:
        return Recipe(kind="classified", palette=palette)
    # Signed/float single-band measurements support a scalar preview. Unsigned
    # codes are ambiguous without a recipe (e.g. classes versus brightness).
    if src.count != 1 or np.dtype(src.dtypes[0]).kind not in {"i", "f"}:
        raise PreviewError(Outcome.NEEDS_REVIEW, "Band meaning requires a rendering recipe")
    data = src.read(1, out_shape=(min(src.height, 512), min(src.width, 512)), masked=True)
    values = data.compressed()
    values = values[np.isfinite(values)]
    if not len(values):
        raise PreviewError(Outcome.NEEDS_REVIEW, "Raster contains no valid preview values")
    lo, hi = map(float, np.percentile(values, (2, 98)))
    if hi <= lo:
        hi = lo + 1
    return Recipe(
        kind="scalar",
        palette=cmap.get("viridis"),
        value_range=(lo, hi),
        nodata=float(src.nodata) if src.nodata is not None and math.isfinite(src.nodata) else None,
        units=src.units[0],
    )


def convert_raster(source: Path, output: Path, budget, supplied: Recipe | None = None):
    verify_tools(budget)
    with rasterio.open(source, driver="GTiff") as src:
        if not src.crs:
            raise PreviewError(Outcome.NEEDS_REVIEW, "Raster CRS missing")
        recipe = raster_recipe(src, supplied)
        bounds = list(transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21))
        if not all(math.isfinite(v) for v in bounds):
            raise PreviewError(Outcome.INVALID, "Invalid raster bounds")
        original = (src.width, src.height, src.count, src.dtypes, src.nodata)
    args = [
        "gdal_translate",
        "-if",
        "GTiff",
        "-of",
        "COG",
        "-co",
        "COMPRESS=LZW",
        "-co",
        "PREDICTOR=YES",
        "-co",
        "OVERVIEW_COMPRESS=LZW",
        "-co",
        "STATISTICS=YES",
        "-co",
        "BLOCKSIZE=512",
        "-co",
        "OVERVIEWS=IGNORE_EXISTING",
        "-co",
        "BIGTIFF=IF_SAFER",
        "-co",
        f"OVERVIEW_RESAMPLING={'NEAREST' if recipe.kind == 'classified' else 'AVERAGE'}",
    ]
    changes = ["Tiled COG with internal overviews; lossless base-image compression"]
    if recipe.max_dimension and max(original[:2]) > recipe.max_dimension:
        scale = recipe.max_dimension / max(original[:2])
        args += [
            "-outsize",
            str(max(1, round(original[0] * scale))),
            str(max(1, round(original[1] * scale))),
            "-r",
            "nearest" if recipe.kind == "classified" else "average",
        ]
        changes.append(f"Resolution reduced to maximum dimension {recipe.max_dimension}")
    run_tool([*args, str(source), str(output)], budget)
    with rasterio.open(output) as result:
        if result.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") != "COG" or not result.is_tiled:
            raise PreviewError(Outcome.INVALID, "Output failed COG layout validation")
        if (
            not recipe.max_dimension
            and (result.width, result.height, result.count, result.dtypes) != original[:4]
        ):
            raise PreviewError(Outcome.INVALID, "COG changed base image dimensions or data types")
        with rasterio.open(source) as src:
            if result.crs != src.crs or not np.allclose(result.bounds, src.bounds):
                raise PreviewError(Outcome.INVALID, "COG changed source georeferencing")
            if result.descriptions != src.descriptions or result.units != src.units:
                raise PreviewError(Outcome.INVALID, "COG changed band meaning or units")
            if result.nodata != src.nodata and not (
                result.nodata is not None
                and src.nodata is not None
                and math.isnan(result.nodata)
                and math.isnan(src.nodata)
            ):
                raise PreviewError(Outcome.INVALID, "COG changed NoData")
            if not recipe.max_dimension:
                for window in (
                    rasterio.windows.Window(0, 0, min(128, src.width), min(128, src.height)),
                    rasterio.windows.Window(
                        max(0, src.width - 128),
                        max(0, src.height - 128),
                        min(128, src.width),
                        min(128, src.height),
                    ),
                ):
                    if not np.array_equal(
                        src.read(window=window), result.read(window=window), equal_nan=True
                    ) or not np.array_equal(
                        src.dataset_mask(window=window), result.dataset_mask(window=window)
                    ):
                        raise PreviewError(Outcome.INVALID, "COG value or mask validation failed")
    footprint = bounds_geometry(bounds)
    coverage = Coverage(
        geometry=mapping(footprint),
        kind="data-footprint",
        label="Data footprint",
        provenance="Georeferenced raster grid bounds (includes NoData areas)",
    )
    return (
        [
            {
                "id": "raster",
                "name": source.stem,
                "path": output,
                "format": "cog",
                "bounds": bounds,
                "recipe": recipe,
            }
        ],
        coverage,
        changes,
    )


def convert_vector(source: Path, output_dir: Path, budget, selected_layer=None, supplied=None):
    verify_tools(budget, vector=True)
    inputs = [source]
    if source.suffix.lower() == ".zip":
        files = extract_zip(source, output_dir / "extracted", budget)
        inputs = sorted(p for p in files if p.suffix.lower() == ".shp")
        for shp in inputs:
            extensions = {
                p.suffix.lower()
                for p in files
                if p.parent == shp.parent and p.stem.lower() == shp.stem.lower()
            }
            if not {".shp", ".shx", ".dbf", ".prj"} <= extensions:
                raise PreviewError(
                    Outcome.NEEDS_REVIEW, "Shapefile is missing companion files or CRS"
                )
    if not inputs:
        raise PreviewError(Outcome.UNSUPPORTED, "Archive contains no shapefiles")
    entries = []
    for path in inputs:
        for name in fiona.listlayers(path):
            if selected_layer is None or name == selected_layer:
                entries.append((path, name))
    if not entries:
        raise PreviewError(Outcome.NEEDS_REVIEW, "Selected layer not found")
    if len(entries) > budget.limits.layers:
        raise PreviewError(Outcome.OVER_LIMIT, "Spatial layer limit exceeded")
    layers, footprints = [], []
    for index, (path, name) in enumerate(entries):
        with fiona.open(
            path, layer=name, enabled_drivers=["ESRI Shapefile", "GPKG", "GeoJSON"]
        ) as src:
            if not src.crs:
                raise PreviewError(Outcome.NEEDS_REVIEW, f"Layer {name} has no CRS")
            if not src.schema.get("geometry") or src.schema["geometry"] == "None":
                continue
            bounds = list(transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21))
            bounds_geometry(bounds)
        sequence = output_dir / f"layer-{index}.fgb"
        output = output_dir / f"layer-{index}.pmtiles"
        run_tool(
            [
                "ogr2ogr",
                "-f",
                "FlatGeobuf",
                "-t_srs",
                "EPSG:4326",
                "-makevalid",
                "-nlt",
                "PROMOTE_TO_MULTI",
                "-lco",
                "SPATIAL_INDEX=YES",
                str(sequence),
                str(path),
                name,
            ],
            budget,
        )
        run_tool(
            [
                "tippecanoe",
                "--force",
                "-o",
                str(output),
                "-l",
                name,
                "-z14" if bounds[0] == bounds[2] and bounds[1] == bounds[3] else "-zg",
                "--drop-densest-as-needed",
                "--extend-zooms-if-still-dropping",
                "--generate-ids",
                str(sequence),
            ],
            budget,
        )
        from pmtiles.reader import Reader

        with output.open("rb") as stream:
            import mmap

            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                reader = Reader(lambda offset, length: mm[offset : offset + length])
                header, meta = reader.header(), reader.metadata()
                if header["addressed_tiles_count"] < 1 or name not in [
                    layer["id"] for layer in meta.get("vector_layers", [])
                ]:
                    raise PreviewError(Outcome.INVALID, "PMTiles layer validation failed")
        recipe = supplied or Recipe(kind="vector")
        if recipe.kind != "vector":
            raise PreviewError(Outcome.NEEDS_REVIEW, "Vector layer requires a vector recipe")
        layers.append(
            {
                "id": f"layer-{index}",
                "name": name,
                "path": output,
                "sequence": sequence,
                "format": "pmtiles",
                "bounds": bounds,
                "recipe": recipe,
            }
        )
        footprints.append(bounds_geometry(bounds))
    if not layers:
        raise PreviewError(Outcome.UNSUPPORTED, "No spatial layers")
    from shapely.ops import unary_union

    coverage = Coverage(
        geometry=mapping(unary_union(footprints)),
        kind="data-footprint",
        label="Data extent",
        provenance="Union of spatial layer extents; gaps may be included",
    )
    return (
        layers,
        coverage,
        [
            (
                "WGS84 FlatGeobuf intermediate; invalid geometry repaired and promoted to multi; "
                "vector tiles generalized by zoom"
            ),
            "Features may be omitted in dense tiles; original download remains authoritative",
            "Generated feature IDs are stable within this derivative version",
        ],
    )
