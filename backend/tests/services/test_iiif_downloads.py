"""IIIF shapes and regressions from public examples in issue #463."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.download_service import DownloadService
from app.services.iiif_downloads import image_downloads, manifest_downloads, service_base

BASE = "https://example.org/iiif/image"
MANIFEST = "https://example.org/manifest"


def v3_manifest(body, **canvas_fields):
    return {
        "items": [
            {
                "id": f"{MANIFEST}/canvas/1",
                "label": {"fr": ["Carte"], "en": ["Map"]},
                "items": [{"items": [{"motivation": "painting", "body": body}]}],
                **canvas_fields,
            }
        ]
    }


def image_body(**extra):
    return {
        "type": "Image",
        "id": f"{BASE}/full/max/0/default.jpg",
        "width": 3000,
        "height": 6000,
        "service": [{"id": BASE, "type": "ImageService3", "profile": "level1"}],
        **extra,
    }


@pytest.mark.parametrize("name,count", [("peace", 1), ("atlas", 3)])
def test_issue_463_contentdm_fixtures(name, count):
    path = Path(__file__).parents[1] / "fixtures" / f"iiif_{name}_463.json"
    downloads = manifest_downloads(json.loads(path.read_text()), MANIFEST)
    assert len(downloads) == count * 5
    assert len({d["canvas_id"] for d in downloads}) == count
    assert all(d["source"] == "iiif" for d in downloads)
    assert all("/full/" in d["url"] for d in downloads)
    if name == "atlas":
        assert list(dict.fromkeys(d["canvas_label"] for d in downloads)) == [
            "Page 1",
            "Page 2",
            "Page 67",
        ]


def test_v3_language_map_and_portrait_sizes():
    downloads = manifest_downloads(v3_manifest(image_body()), MANIFEST)
    assert downloads[0]["canvas_label"] == "Map"
    assert downloads[0]["url"] == f"{BASE}/full/75,/0/default.jpg"
    assert downloads[-1]["url"] == f"{BASE}/full/max/0/default.jpg"
    assert downloads[-1]["label"] == "Largest Available Image"


def test_service_array_ignores_auth_service():
    body = image_body()
    body["service"].insert(0, {"id": "https://example.org/login", "type": "AuthCookieService1"})
    assert manifest_downloads(v3_manifest(body), MANIFEST)[0]["url"].startswith(BASE)


def test_plain_images_choices_renderings_and_nonpainting_annotations():
    body = {
        "type": "Choice",
        "items": [
            {"type": "Image", "id": "https://example.org/a.png", "format": "image/png"},
            {"type": "Image", "id": "https://example.org/b.jpg", "format": "image/jpeg"},
        ],
    }
    manifest = v3_manifest(
        body, rendering={"id": "https://example.org/page.pdf", "label": {"none": ["Page PDF"]}}
    )
    manifest["rendering"] = [
        {"id": "https://example.org/atlas.pdf", "label": "Atlas PDF", "format": "application/pdf"}
    ]
    manifest["items"][0]["items"][0]["items"].append(
        {"motivation": "commenting", "body": image_body()}
    )
    downloads = manifest_downloads(manifest, MANIFEST)
    assert len(downloads) == 4
    assert "canvas_id" not in downloads[0]
    assert downloads[1]["canvas_label"] == "Map"
    assert downloads[2]["label"] == "Image 1: Download Image"
    assert downloads[2]["type"] == "image/png"
    assert downloads[3]["url"] == "https://example.org/b.jpg"


def test_level_zero_uses_only_advertised_sizes_and_max():
    service = {
        "type": "ImageService3",
        "profile": "level0",
        "sizes": [{"width": 100, "height": 200}],
    }
    assert [d["url"] for d in image_downloads(BASE, service)] == [
        f"{BASE}/full/100,200/0/default.jpg",
        f"{BASE}/full/max/0/default.jpg",
    ]


def test_v2_limits_and_no_upscaling():
    service = {
        "width": 4000,
        "height": 2000,
        "profile": [
            "http://iiif.io/api/image/2/level1.json",
            {"maxWidth": 1000, "maxArea": 125000},
        ],
    }
    downloads = image_downloads(BASE, service)
    widths = [int(d["url"].split("/full/")[1].split(",")[0]) for d in downloads]
    assert max(widths) <= 500
    small = image_downloads(BASE, {"width": 50, "height": 100})
    assert small[0]["url"] == f"{BASE}/full/50,/0/default.jpg"


@pytest.mark.parametrize("suffix", ["/", "/info.json", "/full/800,/0/default.jpg"])
def test_normalize_service_urls_preserves_encoded_identifier_and_query(suffix):
    url = f"https://example.org/iiif/a%2Fb{suffix}?token=public"
    assert service_base(url) == "https://example.org/iiif/a%2Fb?token=public"
    assert (
        image_downloads(url)[0]["url"]
        == "https://example.org/iiif/a%2Fb/full/150,/0/default.jpg?token=public"
    )


def test_image_api_one_native_quality():
    downloads = image_downloads(
        BASE,
        {
            "@context": "http://library.stanford.edu/iiif/image-api/1.1/context.json",
            "profile": "http://iiif.io/api/image/1/level1.json",
        },
    )
    assert downloads[-1]["url"].endswith("/full/full/0/native.jpg")


@pytest.mark.parametrize(
    "manifest",
    [None, [], {}, {"items": [None, "remote", {"items": [None]}]}, {"sequences": [None]}],
)
def test_malformed_or_external_only_manifests_are_safe(manifest):
    assert manifest_downloads(manifest, MANIFEST) == []


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:image/png;base64,x",
        "file:///tmp/x",
        "https://user:pass@example.org/image",
    ],
)
def test_unsafe_links_are_not_emitted(url):
    assert image_downloads(url) == []
    assert manifest_downloads(v3_manifest({"type": "Image", "id": url}), MANIFEST) == []


def test_repeated_urls_deduplicate_within_page_but_keep_distinct_pages():
    manifest = v3_manifest([image_body(), image_body()])
    manifest["items"].append({**manifest["items"][0], "id": f"{MANIFEST}/canvas/2"})
    downloads = manifest_downloads(manifest, MANIFEST)
    assert len(downloads) == 10
    assert downloads[0]["image_occurrences"] == [0, 1]
    assert downloads[-1]["image_occurrences"] == [2, 3]


@pytest.mark.asyncio
async def test_manifest_resolution_uses_cache_fetch_once_and_supports_https_reference_key():
    service = DownloadService(
        {"dct_references_s": {"https://iiif.io/api/presentation#manifest": {"url": MANIFEST}}}
    )
    with patch(
        "app.services.image_service.ImageService._get_manifest",
        return_value=v3_manifest(image_body()),
    ) as fetch:
        downloads = await service.resolve_iiif_downloads()
    fetch.assert_called_once_with(MANIFEST)
    assert len(downloads) == 5


@pytest.mark.asyncio
async def test_image_info_version_and_manifest_failure_fallback():
    service = DownloadService(
        {
            "dct_references_s": {
                "http://iiif.io/api/presentation#manifest": MANIFEST,
                "http://iiif.io/api/image": BASE + "/info.json",
            }
        }
    )
    with patch(
        "app.services.image_service.ImageService._get_manifest",
        side_effect=[None, {"type": "ImageService3"}],
    ):
        downloads = await service.resolve_iiif_downloads()
    assert downloads[-1]["url"] == f"{BASE}/full/max/0/default.jpg"


@pytest.mark.asyncio
async def test_unavailable_manifest_signals_retry_without_losing_direct_downloads():
    service = DownloadService(
        {
            "dct_references_s": {
                "http://iiif.io/api/presentation#manifest": MANIFEST,
                "http://schema.org/downloadUrl": "https://example.org/map.pdf",
            }
        }
    )
    with patch("app.services.image_service.ImageService._get_manifest", return_value=None):
        with pytest.raises(ValueError, match="unavailable"):
            await service.resolve_iiif_downloads()
    assert service.get_download_options()[0]["url"] == "https://example.org/map.pdf"


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [False, True])
async def test_download_endpoint_merges_iiif_and_preserves_other_downloads(unavailable):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from app.api.v1.endpoint_modules.resources import downloads as endpoint

    row = SimpleNamespace(_mapping={"id": "atlas"})
    session = AsyncMock()
    session.execute.return_value = MagicMock(fetchone=lambda: row)
    direct = {"label": "Source PDF", "url": "https://example.org/source.pdf"}
    provisional = {"label": "Small Image", "url": "https://example.org/old.jpg", "source": "iiif"}
    resolved = manifest_downloads(v3_manifest(image_body()), MANIFEST)
    with (
        patch.object(endpoint, "async_session") as session_factory,
        patch.object(endpoint, "fetch_distribution_context", new_callable=AsyncMock) as context,
        patch.object(
            endpoint.DownloadService,
            "get_download_options_with_bridge_asset_downloads",
            new_callable=AsyncMock,
            return_value=[direct, provisional],
        ),
        patch.object(
            endpoint.DownloadService, "resolve_iiif_downloads", new_callable=AsyncMock
        ) as resolve,
    ):
        session_factory.return_value.__aenter__.return_value = session
        context.return_value = SimpleNamespace(by_uri={})
        if unavailable:
            resolve.side_effect = ValueError("unavailable")
        else:
            resolve.return_value = resolved
        response = await endpoint.get_resource_downloads(None, "atlas", callback=None)
    payload = json.loads(response.body)
    assert payload["iiif_error"] is unavailable
    assert payload["downloads"] == ([direct, provisional] if unavailable else [direct, *resolved])


@pytest.mark.asyncio
async def test_both_preview_sources_have_downloads_and_stable_image_identity():
    image_url = "https://example.org/standalone/info.json"
    service = DownloadService(
        {
            "dct_references_s": {
                "http://iiif.io/api/presentation#manifest": MANIFEST,
                "http://iiif.io/api/image": image_url,
            }
        }
    )
    with patch(
        "app.services.image_service.ImageService._get_manifest",
        side_effect=[v3_manifest(image_body()), {"type": "ImageService3"}],
    ) as fetch:
        downloads = await service.resolve_iiif_downloads()
    assert fetch.call_count == 2
    assert len(downloads) == 10
    assert {item["iiif_resource_url"] for item in downloads} == {MANIFEST, image_url}
    assert downloads[0]["image_source"] == BASE
    assert downloads[-1]["image_source"] == "https://example.org/standalone"


def test_multiple_images_in_a_canvas_keep_individual_source_identity():
    second = image_body()
    second["service"][0]["id"] = "https://example.org/second"
    downloads = manifest_downloads(v3_manifest([image_body(), second]), MANIFEST)
    assert len(downloads) == 10
    assert len({item["canvas_id"] for item in downloads}) == 1
    assert {item["image_source"] for item in downloads} == {BASE, "https://example.org/second"}


def test_v2_multiple_sequences_follow_viewer_order():
    body = {"@type": "dctypes:Image", "@id": "https://example.org/one.jpg"}
    manifest = {
        "sequences": [
            {
                "canvases": [
                    {"@id": "https://example.org/canvas/one", "images": [{"resource": body}]}
                ]
            },
            {
                "canvases": [
                    {
                        "@id": "https://example.org/canvas/two",
                        "images": [{"resource": {**body, "@id": "https://example.org/two.jpg"}}],
                    }
                ]
            },
        ]
    }
    downloads = manifest_downloads(manifest, MANIFEST)
    assert [item["image_source"] for item in downloads] == [
        "https://example.org/one.jpg",
        "https://example.org/two.jpg",
    ]
