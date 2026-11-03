import hashlib
import json
from contextlib import asynccontextmanager
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.services.preview_assets.models import Limits, Outcome
from app.services.preview_assets.pipeline import Pipeline
from app.services.preview_assets.sources import Source
from app.services.preview_assets.storage import LocalStorage


def fixture(version=3, pages=2):
    source = "https://provider.example/manifest"
    canvases = []
    for n in range(pages):
        cid = f"https://provider.example/canvas/{n}"
        body = {
            "id": f"https://provider.example/image/{n}",
            "type": "Image",
            "service": [{"id": f"https://provider.example/service/{n}", "type": "ImageService3"}],
        }
        if version == 3:
            canvases.append(
                {
                    "id": cid,
                    "type": "Canvas",
                    "width": 701,
                    "height": 533,
                    "label": {"en": [f"Page {n}"]},
                    "items": [
                        {
                            "id": cid + "/page",
                            "type": "AnnotationPage",
                            "items": [
                                {
                                    "id": cid + "/painting",
                                    "type": "Annotation",
                                    "motivation": "painting",
                                    "target": cid,
                                    "body": body,
                                }
                            ],
                        }
                    ],
                }
            )
        else:
            body["@id"], body["@type"] = body.pop("id"), "dctypes:Image"
            body.pop("type")
            canvases.append(
                {
                    "@id": cid,
                    "@type": "sc:Canvas",
                    "width": 701,
                    "height": 533,
                    "images": [{"@id": cid + "/painting", "on": cid, "resource": body}],
                }
            )
    manifest = {
        "@context": f"http://iiif.io/api/presentation/{version}/context.json",
        "id" if version == 3 else "@id": source,
        "label": "Example",
        "rights": "https://creativecommons.org/publicdomain/zero/1.0/",
    }
    manifest.update(
        {"items": canvases} if version == 3 else {"sequences": [{"canvases": canvases}]}
    )
    img = Image.effect_noise((701, 533), 40).convert("RGB")
    buf = BytesIO()
    img.save(buf, "JPEG")
    payloads = {source: json.dumps(manifest).encode()}
    for n in range(pages):
        base = f"https://provider.example/service/{n}"
        payloads[base + "/info.json"] = json.dumps(
            {"type": "ImageService3", "width": 701, "height": 533}
        ).encode()
        payloads[base + "/full/max/0/default.jpg"] = buf.getvalue()

    def fetch(url, path, budget):
        data = payloads[url]
        budget.read(len(data))
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    return source, fetch, payloads


@pytest.mark.parametrize("version", [2, 3])
def test_complete_manifest_tiles_and_offline_delivery(tmp_path, monkeypatch, version):
    from app.api.v1.endpoint_modules import preview_assets as route

    url, fetch, payloads = fixture(version)
    store = LocalStorage(tmp_path / "store")
    result = Pipeline(store, fetch=fetch).prepare(
        {"id": "test", "dct_accessRights_s": "Public"}, source=Source(url, "iiif-manifest")
    )
    assert result.status == Outcome.READY, result.detail
    assert result.metrics["iiif_canvases"] == 2
    assert result.scope == "resource"
    assert result.thumbnail_scope == "sample"
    active = result.model_dump(mode="json")

    @asynccontextmanager
    async def session():
        yield None

    async def published(*args):
        return active

    monkeypatch.setattr(route, "async_session", session)
    monkeypatch.setattr(route, "published_for", published)
    monkeypatch.setattr(route, "storage", lambda: store)
    app = FastAPI()
    app.include_router(route.router, prefix="/api/v1")
    # Remove the upstream completely: every advertised page/tile must still work.
    payloads.clear()
    with TestClient(app) as client:
        for relative, key in result.iiif_assets.items():
            response = client.get("/api/v1/resources/test/preview-assets/" + relative)
            assert response.status_code == 200, relative
            assert response.headers["access-control-allow-origin"] == "*"
            assert response.content == store.path(key).read_bytes()
            if relative.endswith("info.json"):
                info = response.json()
                base = info["@id"].split("localhost:8000")[1]
                assert info["profile"][0].endswith("level0.json")
                assert client.get(base + "/full/full/0/default.jpg").status_code == 200
                for factor in info["tiles"][0]["scaleFactors"]:
                    for y in range(0, 533, 512 * factor):
                        for x in range(0, 701, 512 * factor):
                            w, h = min(512 * factor, 701 - x), min(512 * factor, 533 - y)
                            import math

                            tile = client.get(
                                base + f"/{x},{y},{w},{h}/{math.ceil(w / factor)},/0/default.jpg"
                            )
                            assert tile.status_code == 200
                            assert Image.open(BytesIO(tile.content)).size == (
                                math.ceil(w / factor),
                                math.ceil(h / factor),
                            )
        manifest = client.get(result.layers[0].url.split("localhost:8000")[1]).json()
        assert manifest["rights"].endswith("/1.0/")
        assert (
            len(manifest.get("items", manifest.get("sequences", [{}])[0].get("canvases", []))) == 2
        )
        active = None
        assert client.get(result.layers[0].url.split("localhost:8000")[1]).status_code == 404


@pytest.mark.parametrize(
    "limits",
    [
        Limits(iiif_canvases=1),
        Limits(iiif_pixels=100),
        Limits(iiif_files=2),
        Limits(output_bytes=100),
    ],
)
def test_iiif_limits_do_not_publish_partial_manifest(tmp_path, limits):
    url, fetch, _ = fixture()
    store = LocalStorage(tmp_path / "store")
    result = Pipeline(store, fetch=fetch, limits=limits).prepare(
        {"id": "test", "dct_accessRights_s": "Public"}, source=Source(url, "iiif-manifest")
    )
    assert result.status == Outcome.OVER_LIMIT
    assert not result.layers and not result.iiif_assets
    assert not store.root.exists()


def test_selectors_need_review(tmp_path):
    url, fetch, payloads = fixture()
    doc = json.loads(payloads[url])
    doc["items"][0]["items"][0]["items"][0]["target"] += "#xywh=0,0,10,10"
    payloads[url] = json.dumps(doc).encode()
    result = Pipeline(LocalStorage(tmp_path / "store"), fetch=fetch).prepare(
        {"id": "test", "dct_accessRights_s": "Public"}, source=Source(url, "iiif-manifest")
    )
    assert result.status == Outcome.NEEDS_REVIEW


def test_failed_manifest_does_not_fall_back_to_image(tmp_path):
    url, fetch, payloads = fixture()
    doc = json.loads(payloads[url])
    doc["items"][0]["items"][0]["items"][0]["target"] += "#xywh=0,0,1,1"
    payloads[url] = json.dumps(doc).encode()
    record = {
        "id": "test",
        "dct_accessRights_s": "Public",
        "dct_references_s": {
            "http://iiif.io/api/presentation#manifest": url,
            "http://iiif.io/api/image": "https://provider.example/service/0",
        },
    }
    result = Pipeline(LocalStorage(tmp_path / "store"), fetch=fetch).prepare(record)
    assert result.status == Outcome.NEEDS_REVIEW
    assert not result.layers


def test_direct_v2_image_rejects_reduced_resolution(tmp_path):
    base = "https://provider.example/service/0"
    _, fetch, payloads = fixture(pages=1)
    payloads[base + "/info.json"] = json.dumps(
        {"@context": "http://iiif.io/api/image/2/context.json", "width": 702, "height": 533}
    ).encode()
    payloads[base + "/full/full/0/default.jpg"] = payloads[base + "/full/max/0/default.jpg"]
    result = Pipeline(LocalStorage(tmp_path / "store"), fetch=fetch).prepare(
        {"id": "test", "dct_accessRights_s": "Public"}, source=Source(base, "iiif")
    )
    assert result.status == Outcome.NEEDS_REVIEW


def test_jpeg_recipe_changes_bundle_identity_and_preserves_dimensions(tmp_path):
    url, fetch, _ = fixture(pages=1)
    record = {"id": "test", "dct_accessRights_s": "Public"}
    store = LocalStorage(tmp_path / "store")
    low = Pipeline(store, fetch=fetch, limits=Limits(iiif_jpeg_quality=70)).prepare(
        record, source=Source(url, "iiif-manifest")
    )
    high = Pipeline(store, fetch=fetch, limits=Limits(iiif_jpeg_quality=90)).prepare(
        record, source=Source(url, "iiif-manifest")
    )
    assert low.status == high.status == Outcome.READY
    assert low.source_fingerprint != high.source_fingerprint
    assert low.metrics["iiif_unique_objects"] < low.metrics["iiif_files"]
    for result in [low, high]:
        for path, key in result.iiif_assets.items():
            if path.endswith("full/full/0/default.jpg"):
                with Image.open(store.path(key)) as image:
                    assert image.size == (701, 533)
