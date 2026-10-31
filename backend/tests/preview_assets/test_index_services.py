import json

import numpy as np
import pytest
from PIL import Image
from shapely.geometry import Point, box, mapping, shape

from app.services.preview_assets.geometry import (
    display_coverage,
    point_regions,
    validate_index_content,
)
from app.services.preview_assets.models import (
    Coverage,
    Layer,
    Manifest,
    Outcome,
    PreviewError,
    Recipe,
    publication_allowed,
)
from app.services.preview_assets.pipeline import Pipeline
from app.services.preview_assets.sources import (
    Source,
    iiif_manifest_image,
    retryable_attempts,
    wms_image,
)
from app.services.preview_assets.storage import LocalStorage


def test_coverage_insets_keep_remote_regions_readable():
    from app.services.preview_assets.coverage_map import panels
    from shapely.geometry import MultiPolygon

    regions = MultiPolygon(
        [
            box(-125, 24, -66, 50),
            box(-170, 51, -130, 71),
            box(-160, 18, -154, 23),
            box(-68, 17, -65, 19),
        ]
    )
    assert len(panels(mapping(regions))) == 4


def test_publication_requires_explicit_resource_selection(monkeypatch):
    monkeypatch.delenv("PREVIEW_APPROVED_RESOURCE_IDS", raising=False)
    assert not publication_allowed("test")
    monkeypatch.setenv("PREVIEW_APPROVED_RESOURCE_IDS", "*, reviewed, another")
    assert publication_allowed("reviewed")
    assert not publication_allowed("unreviewed")
    assert not publication_allowed("*")


@pytest.mark.asyncio
async def test_unapproved_resource_never_reads_published_assets(monkeypatch):
    from app.services.preview_assets.repository import published_for

    monkeypatch.setenv("PREVIEW_ASSETS_ENABLED", "true")
    monkeypatch.delenv("PREVIEW_APPROVED_RESOURCE_IDS", raising=False)
    assert await published_for("unreviewed", None) is None


@pytest.mark.parametrize("version", [2, 3])
def test_iiif_manifest_embedded_painting_and_sample(version):
    body = {
        "type": "Image",
        "id": "https://example.org/full.jpg",
        "service": [{"id": "https://example.org/iiif/image", "type": "ImageService3"}],
    }
    if version == 2:
        body["@type"] = body.pop("type").replace("Image", "dctypes:Image")
        canvas = {"images": [{"resource": body}]}
        manifest = {"sequences": [{"canvases": [canvas, canvas]}]}
    else:
        canvas = {"items": [{"items": [{"motivation": "painting", "body": body}]}]}
        manifest = {"items": [canvas, canvas]}
    source, sample = iiif_manifest_image(manifest)
    assert source == Source("https://example.org/iiif/image", "iiif")
    assert sample is True


def test_iiif_composite_needs_review():
    body = {"@type": "dctypes:Image", "@id": "https://example.org/image.jpg"}
    manifest = {"sequences": [{"canvases": [{"images": [{"resource": body}, {"resource": body}]}]}]}
    with pytest.raises(PreviewError, match="composition"):
        iiif_manifest_image(manifest)


def test_wms_respects_referenced_version_and_projects_bounds():
    from urllib.parse import parse_qs, urlsplit

    source = Source("https://example.org/wms?VERSION=1.1.1&SRS=EPSG:3857", "wms", "roads")
    params = parse_qs(urlsplit(wms_image(source, {"dcat_bbox": "-90,40,-89,41"})).query)
    assert params["VERSION"] == ["1.1.1"]
    assert params["SRS"] == ["EPSG:3857"]
    assert [float(v) for v in params["BBOX"][0].split(",")] == pytest.approx(
        [-10018754.17, 4865942.28, -9907434.68, 5012341.66], abs=0.01
    )


def index(member_id=None, direct=None):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(box(-92, 44, -91, 45)),
                "properties": {"recordIdentifier": member_id, "downloadUrl": direct},
            }
        ],
    }


def test_index_one_child_hop_and_collection_coverage(tmp_path):
    child = {
        "id": "child",
        "dct_accessRights_s": "Public",
        "dct_references_s": {"http://schema.org/downloadUrl": "https://example.org/image.jpg"},
    }
    image = tmp_path / "image.png"
    Image.fromarray(np.random.default_rng(4).integers(0, 255, (40, 40, 3), dtype="uint8")).save(
        image
    )

    def fetch(url, target, budget):
        target.write_bytes(
            image.read_bytes() if url.endswith(".jpg") else json.dumps(index("child")).encode()
        )
        budget.read(target.stat().st_size)
        return "fixed"

    looked_up = []

    def lookup(identifier):
        looked_up.append(identifier)
        return child

    result = Pipeline(LocalStorage(tmp_path / "assets"), fetch=fetch, child_lookup=lookup).prepare(
        {"id": "collection", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/index.json", "index"),
    )
    assert result.status == Outcome.READY
    assert result.scope == "sample"
    assert result.coverage.kind == "indexed-coverage"
    assert shape(result.coverage.geometry).bounds == (-92, 44, -91, 45)
    assert looked_up == ["child"]
    assert result.dependencies[0]["resource_id"] == "child"
    assert "/resources/collection/" in result.thumbnail_url


@pytest.mark.parametrize("identifier,detail", [("parent", "cycle"), ("grandchild", "hop limit")])
def test_index_cycle_and_second_hop_are_not_followed(tmp_path, identifier, detail):
    def fetch(url, target, budget):
        target.write_text(json.dumps(index("child" if url.endswith("parent") else identifier)))
        return "fixed"

    def lookup(value):
        assert value == "child"
        return {
            "id": "child",
            "dct_accessRights_s": "Public",
            "dct_references_s": {"https://openindexmaps.org": "https://example.org/child"},
        }

    result = Pipeline(LocalStorage(tmp_path / "assets"), fetch=fetch, child_lookup=lookup).prepare(
        {"id": "parent", "dct_accessRights_s": "Public"},
        source=Source("https://example.org/parent", "index"),
    )
    assert result.status == Outcome.NEEDS_REVIEW
    assert detail in result.detail
    assert result.coverage.kind == "indexed-coverage"


def test_display_geometry_is_simplified_once_with_provenance():
    geometry = Point(-90, 40).buffer(1, quad_segs=1000)
    coverage = Coverage(
        geometry=mapping(geometry),
        kind="data-footprint",
        label="Data footprint",
        provenance="Verified input",
    )
    shown = display_coverage(coverage)
    assert shape(shown.geometry).is_valid
    assert len(shown.geometry["coordinates"][0]) < len(coverage.geometry["coordinates"][0])
    assert "source geometry SHA256" in shown.provenance
    assert display_coverage(shown) == shown


def test_regional_point_extents_retain_remote_and_dateline_groups():
    points = [(-120, 40), (-119, 41), (-155, 20), (-154, 21), (179, 50), (-179, 50)]
    regions = point_regions(points)
    assert all(regions.covers(Point(*point)) for point in points)
    assert not regions.covers(Point(0, 50))
    assert not regions.covers(Point(-137, 30))
    assert regions.equals(point_regions(reversed(points)))


def test_index_content_conflicts_are_withheld():
    manifest = Manifest(
        status=Outcome.READY,
        layers=[
            Layer(
                id="a",
                name="a",
                url="https://example.org/a.tif",
                format="cog",
                recipe=Recipe(kind="rgb", bands=[1, 2, 3]),
                bounds=[-92, 44, -91, 45],
            )
        ],
    )
    member = index()["features"][0]
    with pytest.raises(PreviewError, match="band meaning"):
        validate_index_content({"dct_title_s": "County DEM"}, member, manifest)
    manifest.layers[0].bounds = [10, 40, 11, 41]
    with pytest.raises(PreviewError, match="outside"):
        validate_index_content({"dct_title_s": "County imagery"}, member, manifest)


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("Source HTTP 503", True),
        ("Source HTTP 404", False),
        ("Provider busy; retry later", True),
        ("Read timed out", True),
        ("Resource is not public", False),
    ],
)
def test_retry_only_transient_source_failures(detail, expected):
    assert bool(retryable_attempts([{"status": "unavailable", "detail": detail}])) is expected
