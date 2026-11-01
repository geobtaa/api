"""Client-facing asset discovery stays consistent with the viewer and delivery gates."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services.preview_assets.models import Coverage, Layer, Manifest, Outcome
from app.services.preview_assets.presentation import public_assets
from app.services.preview_assets.repository import attach_preview

COVERAGE = Coverage(kind="metadata-extent", label="Metadata extent", provenance="Record bounds")


@pytest.mark.parametrize(
    "format",
    ["cog", "pmtiles", "parquet", "iiif", "iiif-manifest", "geojson", "wms", "arcgis", "image"],
)
def test_clients_can_discover_every_supported_layer(format):
    manifest = Manifest(
        status=Outcome.READY,
        scope="sample",
        coverage=COVERAGE,
        layers=[
            Layer(
                id="one",
                name="Example",
                format=format,
                url="https://example.org/asset",
                source_layer="features",
                columns=[{"name": "id", "type": "BIGINT"}],
                row_count=25,
            )
        ],
        thumbnail_status=Outcome.READY,
        thumbnail_url="https://example.org/thumb.png",
        thumbnail_scope="sample",
        coverage_url="https://example.org/coverage.png",
        iiif_assets={"private": "object-key"},
        metrics={"private": "diagnostic"},
    ).model_dump(mode="json")
    assets = public_assets(manifest, manifest["coverage"])
    layer, thumbnail, location = assets["items"]
    assert layer["url"] == manifest["layers"][0]["url"]
    assert layer["layer_id"] == "one"
    assert layer["source_layer"] == "features"
    assert layer["roles"] == (["table"] if format == "parquet" else ["visualization"])
    assert layer["scope"] == thumbnail["scope"] == "sample"
    assert location["scope"] == "resource"
    assert assets["coverage"]["label"] == "Metadata extent"
    assert "byte_size" not in layer
    assert not {"asset_key", "iiif_assets", "metrics"} & layer.keys()
    if format == "parquet":
        assert layer["columns"] == [{"name": "id", "type": "BIGINT"}]
        assert layer["row_count"] == 25
        assert layer["media_type"] == "application/vnd.apache.parquet"


def test_unpublished_content_is_not_advertised():
    manifest = Manifest(
        status=Outcome.NEEDS_REVIEW,
        layers=[Layer(id="one", name="Example", format="cog", url="https://example.org/asset")],
        thumbnail_status=Outcome.NEEDS_REVIEW,
        thumbnail_url="https://example.org/review.png",
    ).model_dump(mode="json")
    assert public_assets(manifest, COVERAGE.model_dump())["items"] == []
    assert public_assets(None, COVERAGE.model_dump())["items"] == []


def test_resource_attachment_exposes_catalog_and_preserves_ui_and_downloads(monkeypatch):
    monkeypatch.setenv("PREVIEW_ASSETS_ENABLED", "true")
    monkeypatch.setenv("PREVIEW_APPROVED_RESOURCE_IDS", "example")
    manifest = Manifest(
        status=Outcome.READY,
        coverage=COVERAGE,
        layers=[Layer(id="one", name="Example", format="pmtiles", url="https://example.org/asset")],
        thumbnail_status=Outcome.READY,
        thumbnail_url="https://example.org/generated.png",
    ).model_dump(mode="json")
    lookup = AsyncMock(return_value=manifest)
    monkeypatch.setattr("app.services.preview_assets.repository.published_for", lookup)
    resource = {
        "attributes": {"downloads": ["original.zip"]},
        "meta": {
            "ui": {"thumbnail_curated": True, "thumbnail_url": "https://example.org/curated.jpg"}
        },
    }
    record = {"id": "example", "dct_accessRights_s": "Public"}
    asyncio.run(attach_preview(resource, record, session=object()))
    assert (
        resource["meta"]["assets"]["items"][0]["url"]
        == resource["meta"]["ui"]["preview"]["layers"][0]["url"]
    )
    assert resource["meta"]["ui"]["thumbnail_url"] == "https://example.org/curated.jpg"
    assert resource["attributes"]["downloads"] == ["original.zip"]
    for updates in ({"dct_accessRights_s": "Restricted"}, {"id": "unapproved"}):
        hidden = {}
        asyncio.run(attach_preview(hidden, {**record, **updates}, session=object()))
        assert "meta" not in hidden
    monkeypatch.setenv("PREVIEW_ASSETS_ENABLED", "false")
    hidden = {}
    asyncio.run(attach_preview(hidden, record, session=object()))
    assert "meta" not in hidden


def test_service_layer_identifier_survives_preparation(tmp_path):
    from PIL import Image

    from app.services.preview_assets.io import Budget
    from app.services.preview_assets.models import Limits
    from app.services.preview_assets.pipeline import Pipeline
    from app.services.preview_assets.sources import Source
    from app.services.preview_assets.storage import LocalStorage

    def fetch(url, target, budget):
        Image.linear_gradient("L").convert("RGB").save(target, format="PNG")
        return "fingerprint"

    record = {"id": "service", "dcat_bbox": "ENVELOPE(-94,-90,46,43)"}
    pipeline = Pipeline(LocalStorage(tmp_path / "store"), fetch=fetch)
    result = pipeline._service(
        record,
        Source("https://example.org/wms", "wms", "roads & paths"),
        tmp_path,
        Budget(Limits(), tmp_path),
    )
    assets = public_assets(result.model_dump(mode="json"), COVERAGE.model_dump())
    assert assets["items"][0]["source_layer"] == "roads & paths"
