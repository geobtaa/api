import json
import os
import shutil
import subprocess
import zipfile

import numpy as np
import pytest
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from app.services.preview_assets.geometry import (
    index_coverage,
    metadata_coverage,
    representative_members,
)
from app.services.preview_assets.io import Budget, extract_zip, public_address
from app.services.preview_assets.models import Limits, Manifest, Outcome, PreviewError, Recipe
from app.services.preview_assets.pipeline import Pipeline
from app.services.preview_assets.repository import next_active
from app.services.preview_assets.sources import Source, arcgis_export, wms_image
from app.services.preview_assets.storage import LocalStorage


@pytest.fixture(scope="session")
def pinned_conversion_tools():
    """The dedicated worker CI job requires these; general API CI may lack them."""
    try:
        gdal = subprocess.check_output(["gdalinfo", "--version"], text=True)
        tiles = subprocess.check_output(
            ["tippecanoe", "--version"], text=True, stderr=subprocess.STDOUT
        )
        available = gdal.startswith("GDAL 3.11.0") and "v2.79.0" in tiles
    except (OSError, subprocess.CalledProcessError):
        available = False
    if not available:
        message = "Conversion tests require GDAL 3.11.0 and Tippecanoe 2.79.0 (Dockerfile.preview)"
        if os.getenv("PREVIEW_REQUIRE_TOOLS") == "true":
            pytest.fail(message)
        pytest.skip(message)


def fixture_fetch(source):
    def fetch(url, target, budget):
        budget.read(source.stat().st_size)
        shutil.copyfile(source, target)
        return "a" * 64

    return fetch


def raster(path, kind):
    width = 640
    data = np.indices((width, width)).sum(axis=0)
    profile = dict(
        driver="GTiff",
        width=width,
        height=width,
        count=3 if kind == "rgb" else 1,
        dtype="uint8" if kind != "scalar" else "float32",
        crs="EPSG:4326",
        transform=from_origin(-92, 45, 0.001, 0.001),
    )
    with rasterio.open(path, "w", **profile) as dst:
        if kind == "rgb":
            dst.write(np.array([data % 256, data // 3 % 256, data // 5 % 256], dtype="uint8"))
            dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
        elif kind == "classified":
            dst.write((data % 3 + 1).astype("uint8"), 1)
            dst.write_colormap(
                1, {1: (0, 100, 0, 255), 2: (50, 90, 200, 255), 3: (220, 160, 50, 255)}
            )
        else:
            dst.write(data.astype("float32"), 1)


@pytest.mark.parametrize("kind", ["rgb", "scalar", "classified"])
@pytest.mark.usefixtures("pinned_conversion_tools")
def test_real_cog_conversion_and_render(tmp_path, kind):
    source = tmp_path / "input.tif"
    raster(source, kind)
    store = LocalStorage(tmp_path / "assets")
    result = Pipeline(store, fetch=fixture_fetch(source)).prepare(
        {"id": "test", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/source.tif", "download"),
    )
    assert result.status == Outcome.READY, result.detail
    assert result.thumbnail_status == Outcome.READY
    assert result.layers[0].recipe.kind == kind
    assert result.layers[0].bounds == pytest.approx([-92, 44.36, -91.36, 45])
    assert store.path(result.thumbnail_key).is_file()
    with rasterio.open(store.path(result.layers[0].asset_key)) as dst:
        assert dst.tags(ns="IMAGE_STRUCTURE")["LAYOUT"] == "COG"
        assert dst.overviews(1)


@pytest.mark.usefixtures("pinned_conversion_tools")
def test_real_vector_conversion(tmp_path):
    source = tmp_path / "input.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "A", "id": 12},
                        "geometry": mapping(box(-92, 44, -91, 45)),
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "B", "id": 13},
                        "geometry": mapping(box(-90.7, 44, -90.5, 45)),
                    },
                ],
            }
        )
    )
    result = Pipeline(LocalStorage(tmp_path / "assets"), fetch=fixture_fetch(source)).prepare(
        {"id": "vector", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/data.geojson", "download"),
    )
    assert result.status == Outcome.READY, result.detail
    assert result.layers[0].format == "pmtiles"
    assert result.thumbnail_status == Outcome.READY


@pytest.mark.parametrize("driver", ["GPKG", "GeoJSON", "ESRI Shapefile"])
@pytest.mark.usefixtures("pinned_conversion_tools")
def test_source_feature_ids_survive_vector_tiles(tmp_path, driver):
    import gzip

    import fiona
    import mapbox_vector_tile
    from pmtiles.reader import all_tiles

    from app.services.preview_assets.convert import convert_vector

    suffix = {"GPKG": ".gpkg", "GeoJSON": ".geojson", "ESRI Shapefile": ".shp"}[driver]
    source = tmp_path / ("identifiers" + suffix)
    # A quoted layer and colliding field exercise query quoting and preservation
    # of existing attributes. Shapefile field names are limited to ten characters.
    name = 'parks "original"' if driver == "GPKG" else "identifiers"
    existing = "__preview_source_fid" if driver != "ESRI Shapefile" else "label"
    with fiona.open(
        source,
        "w",
        driver=driver,
        layer=name,
        schema={"geometry": "Point", "properties": {existing: "str", "rowid": "str"}},
        crs="EPSG:4326",
    ) as collection:
        for index, point in enumerate([(-91, 44), (-90, 45)]):
            collection.write(
                {
                    "geometry": {"type": "Point", "coordinates": point},
                    "properties": {existing: f"original-{index}", "rowid": f"attribute-{index}"},
                }
            )
    if driver == "GPKG":
        subprocess.run(
            [
                "ogrinfo",
                str(source),
                "-sql",
                'UPDATE "parks ""original""" SET fid=fid+9007199254740992',
            ],
            check=True,
            capture_output=True,
        )
    elif driver == "GeoJSON":
        content = json.loads(source.read_text())
        for index, feature in enumerate(content["features"]):
            feature["id"] = 9007199254740993 + index
        source.write_text(json.dumps(content))
    with fiona.open(source, layer=name) as collection:
        expected = {f["properties"][existing]: f.id for f in collection}
    layers, _, changes = convert_vector(source, tmp_path, Budget(Limits(), tmp_path))
    field = "__preview_source_fid" + ("_" if driver != "ESRI Shapefile" else "")
    assert any(field in change for change in changes)
    content = layers[0]["path"].read_bytes()
    observed = {}
    for _, data in all_tiles(lambda offset, size: content[offset : offset + size]):
        for layer in mapbox_vector_tile.decode(gzip.decompress(data)).values():
            for feature in layer["features"]:
                properties = feature["properties"]
                assert properties["rowid"].startswith("attribute-")
                observed[properties[existing]] = properties[field]
    assert observed == expected
    assert all(isinstance(value, str) for value in observed.values())


def test_archive_rejects_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape.shp", b"bad")
    with pytest.raises(PreviewError, match="Unsafe"):
        extract_zip(archive, tmp_path / "out", Budget(Limits(), tmp_path))
    assert not (tmp_path.parent / "escape.shp").exists()


def test_archive_rejects_expansion(tmp_path):
    archive = tmp_path / "large.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("large.shp", b"x" * 100)
    with pytest.raises(PreviewError, match="expansion"):
        extract_zip(archive, tmp_path / "out", Budget(Limits(extracted_bytes=99), tmp_path))


def test_private_source_rejected():
    with pytest.raises(PreviewError, match="Non-public"):
        public_address("http://127.0.0.1/data.tif")


def test_failed_refresh_keeps_last_good():
    good = Manifest(status=Outcome.READY).model_dump(mode="json")
    assert next_active(good, Manifest(status=Outcome.UNAVAILABLE)) == good


def test_restricted_source_never_fetched(tmp_path):
    def fetch(*args):
        pytest.fail("Restricted resource was fetched")

    result = Pipeline(LocalStorage(tmp_path), fetch=fetch).prepare(
        {"id": "restricted", "dct_accessRights_s": "Restricted"}
    )
    assert result.status == Outcome.UNAVAILABLE


def test_wms_axis_order_and_layer_encoding():
    from urllib.parse import parse_qs, urlsplit

    record = {"dcat_bbox": "ENVELOPE(-94,-90,46,43)"}
    source = Source("https://example.org/wms?token=public", "wms", "roads & paths")
    p = parse_qs(urlsplit(wms_image(source, record)).query)
    assert p["BBOX"] == ["43.0,-94.0,46.0,-90.0"]
    assert p["LAYERS"] == ["roads & paths"]
    p = parse_qs(urlsplit(wms_image(source, record, "1.1.1")).query)
    assert p["BBOX"] == ["-94.0,43.0,-90.0,46.0"]
    assert p["SRS"] == ["EPSG:4326"]


def test_arcgis_layer_export_preserves_layer():
    url = arcgis_export(
        "https://example.org/rest/services/a/MapServer/4",
        {
            "extent": {
                "xmin": 1,
                "ymin": 2,
                "xmax": 3,
                "ymax": 4,
                "spatialReference": {"wkid": 4326},
            }
        },
    )
    assert "/MapServer/export?" in url
    assert "layers=show%3A4" in url


def test_index_coverage_is_not_sample_extent():
    collection = {
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(box(x, 40, x + 1, 41)),
                "properties": {"label": str(x)},
            }
            for x in [-95, -90, -85, -80]
        ]
    }
    assert index_coverage(collection).kind == "indexed-coverage"
    assert len(representative_members(collection)) == 3
    assert representative_members(collection) == representative_members(
        {"features": list(reversed(collection["features"]))}
    )


def test_missing_geometry_has_no_world_fallback():
    assert metadata_coverage({}).kind == "unavailable"
    assert metadata_coverage({}).geometry is None


def test_recipe_rejects_unknown_class_palette():
    with pytest.raises(ValueError):
        Recipe(kind="classified")


@pytest.mark.usefixtures("pinned_conversion_tools")
def test_zip_geopackage_all_layers_and_ids(tmp_path):
    import fiona

    source = tmp_path / "multi.gpkg"
    for name in ["roads", "parks"]:
        with fiona.open(
            source,
            "w",
            driver="GPKG",
            layer=name,
            schema={"geometry": "Polygon", "properties": {"name": "str"}},
            crs="EPSG:4326",
        ) as collection:
            collection.write(
                {"geometry": mapping(box(-92, 44, -91, 45)), "properties": {"name": name}}
            )
    archive = tmp_path / "multi.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(source, "multi.gpkg")
    result = Pipeline(LocalStorage(tmp_path / "assets"), fetch=fixture_fetch(archive)).prepare(
        {"id": "multi", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/multi.gpkg.zip", "download"),
    )
    assert result.status == Outcome.READY, result.detail
    assert [layer.name for layer in result.layers] == ["roads", "parks"]
    assert len({layer.id for layer in result.layers}) == 2
    assert result.thumbnail_scope == "sample"


@pytest.mark.usefixtures("pinned_conversion_tools")
def test_missing_crs_is_not_guessed(tmp_path):
    source = tmp_path / "unlocated.tif"
    with rasterio.open(
        source, "w", driver="GTiff", width=16, height=16, count=1, dtype="float32"
    ) as dst:
        dst.write(np.ones((16, 16), dtype="float32"), 1)
    result = Pipeline(LocalStorage(tmp_path / "assets"), fetch=fixture_fetch(source)).prepare(
        {"id": "unlocated", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/unlocated.tif", "download"),
    )
    assert result.status == Outcome.NEEDS_REVIEW
    assert not result.layers


def test_dateline_and_holes_are_preserved():
    from shapely.geometry import Polygon, shape

    from app.services.preview_assets.geometry import normalized_geometry

    geom = normalized_geometry("ENVELOPE(170,-170,60,50)")
    assert geom.geom_type == "MultiPolygon"
    assert geom.area == pytest.approx(200)
    donut = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], holes=[[(2, 2), (3, 2), (3, 3), (2, 3)]])
    assert shape(metadata_coverage({"locn_geometry": mapping(donut)}).geometry).area == 99


@pytest.mark.usefixtures("pinned_conversion_tools")
def test_output_limit_prevents_publication(tmp_path):
    source = tmp_path / "source.tif"
    raster(source, "rgb")
    store = LocalStorage(tmp_path / "assets")
    result = Pipeline(store, limits=Limits(output_bytes=1), fetch=fixture_fetch(source)).prepare(
        {"id": "limited", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/source.tif", "download"),
    )
    assert result.status == Outcome.OVER_LIMIT
    assert not store.root.exists()


def test_resource_signature_detects_source_withdrawal():
    from app.services.preview_assets.repository import record_signature

    original = {
        "id": "one",
        "dct_references_s": '{"http://schema.org/downloadUrl":"https://example.org/data.zip"}',
    }
    assert record_signature(original) != record_signature({**original, "dct_references_s": "{}"})


def test_local_asset_immutable_and_range_delivery(tmp_path):
    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.testclient import TestClient

    source = tmp_path / "sample.pmtiles"
    source.write_bytes(b"0123456789")
    store = LocalStorage(tmp_path / "assets")
    key = store.put(source)
    assert key == store.put(source)
    app = FastAPI()

    @app.get("/asset")
    def asset():
        return FileResponse(store.path(key))

    with TestClient(app) as client:
        response = client.get("/asset", headers={"Range": "bytes=2-5"})
        assert response.status_code == 206
        assert response.content == b"2345"
        assert response.headers["content-range"] == "bytes 2-5/10"


def test_unknown_access_does_not_download(tmp_path):
    def fetch(*args):
        pytest.fail("Unknown access was treated as public")

    result = Pipeline(LocalStorage(tmp_path), fetch=fetch).prepare({"id": "unknown"})
    assert result.status == Outcome.UNAVAILABLE


@pytest.mark.usefixtures("pinned_conversion_tools")
def test_single_point_vector_has_valid_coverage(tmp_path):
    source = tmp_path / "point.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Only point"},
                        "geometry": {"type": "Point", "coordinates": [-92, 45]},
                    }
                ],
            }
        )
    )
    result = Pipeline(LocalStorage(tmp_path / "assets"), fetch=fixture_fetch(source)).prepare(
        {"id": "point", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/point.geojson", "download"),
    )
    assert result.status == Outcome.READY, result.detail
    assert result.coverage.geometry["type"] == "Point"


def test_curated_sources_take_precedence_and_invalidate():
    from app.services.preview_assets.repository import record_signature
    from app.services.preview_assets.sources import COG, discover

    record = {
        "dct_references_s": json.dumps({COG: "https://example.org/old.tif"}),
        "_preview_sources": [{"uri": COG, "url": "https://example.org/assigned.tif"}],
    }
    assert discover(record)[0].url.endswith("/assigned.tif")
    assert record_signature(record) != record_signature({**record, "_preview_sources": []})


def test_actual_asset_route_range_and_access_gate(tmp_path, monkeypatch, caplog):
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.endpoint_modules import preview_assets as route

    source = tmp_path / "source.pmtiles"
    source.write_bytes(b"0123456789")
    store = LocalStorage(tmp_path / "assets")
    key = store.put(source)
    active = {"status": "ready", "layers": [{"asset_key": key}]}

    @asynccontextmanager
    async def session():
        yield None

    async def published(identifier, session):
        return active

    monkeypatch.setattr(route, "async_session", session)
    monkeypatch.setattr(route, "published_for", published)
    monkeypatch.setattr(route, "storage", lambda: store)
    app = FastAPI()
    app.include_router(route.router)
    caplog.set_level("INFO", logger="app.services.preview_assets.metrics")
    with TestClient(app) as client:
        url = f"/resources/test/preview-assets/{key}"
        response = client.get(url, headers={"Range": "bytes=3-6"})
        assert response.status_code == 206
        assert response.content == b"3456"
        assert response.headers["access-control-allow-origin"] == "*"
        assert client.head(url).content == b""
        active = None
        assert client.get(url).status_code == 404
    deliveries = [
        entry.preview_delivery for entry in caplog.records if hasattr(entry, "preview_delivery")
    ]
    assert [(item["status"], item["bytes"], item["complete"]) for item in deliveries] == [
        (206, 4, True),
        (200, 0, True),
    ]


@pytest.mark.usefixtures("pinned_conversion_tools")
def test_tiff_companion_crs_survives_isolated_conversion(tmp_path):
    from app.services.preview_assets.convert import convert_raster

    source = tmp_path / "sidecar.tif"
    original = tmp_path / "original.tif"
    raster(original, "classified")
    # Move authoritative georeferencing from the TIFF into the supplied PAM file.
    with rasterio.open(original) as dataset:
        profile = dataset.profile.copy()
        profile.pop("crs")
        with rasterio.open(source, "w", **profile) as target:
            target.write(dataset.read())
            target.write_colormap(1, dataset.colormap(1))
    (tmp_path / "sidecar.tif.aux.xml").write_text("<PAMDataset><SRS>EPSG:4326</SRS></PAMDataset>")
    budget = Budget(Limits(), tmp_path)
    layers, _, _ = convert_raster(source, tmp_path / "converted.tif", budget)
    with rasterio.open(layers[0]["path"]) as result:
        assert result.crs.to_epsg() == 4326
        assert result.colormap(1)[1] == (0, 100, 0, 255)


def test_suspicious_dark_image_is_reviewed_not_accepted(tmp_path):
    from PIL import Image

    from app.services.preview_assets.render import quality

    image = Image.fromarray(np.random.default_rng(42).integers(0, 12, (64, 64, 3), dtype="uint8"))
    path = tmp_path / "dark.png"
    image.save(path)
    assert quality(path) == Outcome.NEEDS_REVIEW


def test_cumulative_archive_and_output_limits(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("one.txt", b"123456")
    budget = Budget(Limits(extracted_bytes=10, output_bytes=10), tmp_path)
    extract_zip(archive, tmp_path / "first", budget)
    with pytest.raises(PreviewError, match="expansion"):
        extract_zip(archive, tmp_path / "second", budget)
    budget.publish(6)
    with pytest.raises(PreviewError, match="Total derivative"):
        budget.publish(5)


def test_interrupted_conversion_has_a_bounded_outcome(tmp_path):
    import sys
    import time

    from app.services.preview_assets.process import run_tool

    started = time.monotonic()
    with pytest.raises(PreviewError, match="Processing time limit") as failure:
        run_tool(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            Budget(Limits(seconds=1), tmp_path),
        )
    assert failure.value.status == Outcome.OVER_LIMIT
    assert time.monotonic() - started < 5


def test_index_omissions_are_explicit_and_invalid_members_not_selected():
    valid = {"geometry": mapping(box(-95, 40, -94, 41)), "properties": {"label": "valid"}}
    collection = {"features": [valid, {"geometry": None}]}
    coverage = index_coverage(collection)
    assert coverage.label == "Indexed coverage (incomplete)"
    assert "1 invalid" in coverage.provenance
    selected = representative_members(collection)
    assert len(selected) == 1
    assert selected[0]["properties"]["label"] == "valid"


def test_object_asset_range_validators_and_missing_objects(monkeypatch):
    from contextlib import asynccontextmanager
    from io import BytesIO

    from botocore.exceptions import ClientError
    from botocore.response import StreamingBody
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.endpoint_modules import preview_assets as route

    key = "a" * 64 + ".pmtiles"

    class Store:
        missing = False
        ranges = []

        def head(self, key):
            if self.missing:
                raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
            return {"ContentLength": 10, "ETag": '"v1"'}

        def get(self, key, byte_range):
            self.ranges.append(byte_range)
            item = self.head(key)
            content = b"0123456789"
            if byte_range:
                content = b"2345"
                item.update(ContentLength=4, ContentRange="bytes 2-5/10")
            return {**item, "Body": StreamingBody(BytesIO(content), len(content))}

    store = Store()

    @asynccontextmanager
    async def session():
        yield None

    async def published(identifier, session):
        return {"status": "ready", "layers": [{"asset_key": key}]}

    monkeypatch.setattr(route, "async_session", session)
    monkeypatch.setattr(route, "published_for", published)
    monkeypatch.setattr(route, "storage", lambda: store)
    app = FastAPI()
    app.include_router(route.router)
    with TestClient(app) as client:
        url = f"/resources/test/preview-assets/{key}"
        assert client.get(url, headers={"Range": "bytes=2-5"}).content == b"2345"
        response = client.get(url, headers={"Range": "bytes=2-5", "If-Range": '"old"'})
        assert response.status_code == 200
        assert store.ranges[-1] is None
        assert client.head(url).headers["content-length"] == "10"
        store.missing = True
        assert client.head(url).status_code == 404
        assert client.get(url).status_code == 404
