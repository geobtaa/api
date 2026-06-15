from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.presenters import ResourceHydrationContext, ResourcePresenter


def _distribution_context():
    return SimpleNamespace(
        legacy_reference_payload={"http://schema.org/url": "https://example.edu/catalog/res-1"},
        by_uri={},
    )


def _thumbnail_url(item, distribution_context=None, hot_only=False):
    return {**item, "ui_thumbnail_url": "https://images.example.edu/res-1-thumb.jpg"}


@pytest.mark.asyncio
async def test_resource_presenter_full_profile_contract_snapshot():
    presenter = ResourcePresenter(session=None)
    immutable_thumbnail_url = f"http://localhost:8000/api/v1/thumbnails/{'a' * 64}"
    hydration = ResourceHydrationContext(
        distribution_context=_distribution_context(),
        ui_downloads=[{"label": "GeoJSON", "url": "https://example.edu/res-1.geojson"}],
        licensed_accesses_payload=[
            {
                "institution_code": "01",
                "institution_name": "Indiana University",
                "access_url": "https://example.edu/license",
            }
        ],
        ui_relationships={"member_of": [{"id": "collection-1", "label": "Collection"}]},
        ui_relationship_counts={"member_of": 1},
        ui_relationship_browse_links={"member_of": "/catalog?member_of=collection-1"},
        allmaps_attributes={"manifest_url": "https://example.edu/iiif/manifest.json"},
        data_dictionaries_payload=[
            {
                "name": "Attributes",
                "entries": [{"field_name": "parcel_id", "label": "Parcel ID"}],
            }
        ],
        thumbnail_asset_url="https://assets.example.edu/res-1-thumb.jpg",
    )

    with (
        patch("app.api.v1.utils.add_thumbnail_url", side_effect=_thumbnail_url),
        patch(
            "app.api.v1.utils._hot_thumbnail_url_for_resource",
            return_value=immutable_thumbnail_url,
        ),
        patch("app.api.v1.utils._hot_static_map_url", return_value=None),
        patch(
            "app.api.v1.utils._build_static_map_url",
            return_value="http://localhost:8000/api/v1/static-maps/res-1/geometry",
        ),
        patch("app.api.v1.utils._get_thumbnail_asset_url", new=AsyncMock()) as get_thumb,
        patch(
            "app.services.citation_service.CitationService.get_all_citations",
            return_value={"apa": "APA", "mla": "MLA", "chicago": "Chicago"},
        ),
        patch(
            "app.services.viewer_service.ViewerService.get_viewer_attributes",
            return_value={
                "ui_viewer_endpoint": "https://tiles.example.edu/res-1",
                "ui_viewer_geometry": "ENVELOPE(-94,-93,45,44)",
                "ui_viewer_protocol": "xyz",
            },
        ),
        patch("app.services.link_service.LinkService.get_links", return_value={"catalog": []}),
    ):
        resource = await presenter.present_full(
            {
                "id": "res-1",
                "dct_title_s": "Sample Resource",
                "schema_provider_s": "Example University",
                "b1g_code_s": "B1G-001",
                "locn_geometry": "ENVELOPE(-94,-93,45,44)",
            },
            apply_field_mapping=False,
            include_similar_items=False,
            hydration=hydration,
        )

    get_thumb.assert_not_awaited()
    assert resource == {
        "type": "resource",
        "id": "res-1",
        "attributes": {
            "ogm": {
                "id": "res-1",
                "dct_title_s": "Sample Resource",
                "dct_references_s": '{"http://schema.org/url": "https://example.edu/catalog/res-1"}',
                "locn_geometry": "ENVELOPE(-94,-93,45,44)",
                "schema_provider_s": "Example University",
            },
            "b1g": {
                "b1g_code_s": "B1G-001",
                "data_dictionaries": [
                    {
                        "name": "Attributes",
                        "entries": [{"field_name": "parcel_id", "label": "Parcel ID"}],
                    }
                ],
            },
        },
        "meta": {
            "@context": "https://gin.btaa.org/ld/contexts/ogm-aardvark-btaa.context.jsonld",
            "@type": "BtaaAardvarkRecord",
            "ui": {
                "thumbnail_url": immutable_thumbnail_url,
                "citation": "APA",
                "citations": {"apa": "APA", "mla": "MLA", "chicago": "Chicago"},
                "downloads": [{"label": "GeoJSON", "url": "https://example.edu/res-1.geojson"}],
                "licensed_accesses": [
                    {
                        "institution_code": "01",
                        "institution_name": "Indiana University",
                        "access_url": "https://example.edu/license",
                    }
                ],
                "links": {"catalog": []},
                "relationships": {"member_of": [{"id": "collection-1", "label": "Collection"}]},
                "relationship_counts": {"member_of": 1},
                "relationship_browse_links": {"member_of": "/catalog?member_of=collection-1"},
                "viewer": {
                    "protocol": "xyz",
                    "endpoint": "https://tiles.example.edu/res-1",
                    "geometry": "ENVELOPE(-94,-93,45,44)",
                },
                "allmaps": {"manifest_url": "https://example.edu/iiif/manifest.json"},
                "static_map": "http://localhost:8000/api/v1/static-maps/res-1/geometry",
            },
        },
    }


@pytest.mark.asyncio
async def test_resource_presenter_search_profile_contract_snapshot():
    presenter = ResourcePresenter(session=None)
    bridge_download_rows = [{"label": "Original", "file_url": "https://example.edu/file.zip"}]
    relationship_service = AsyncMock()

    with (
        patch("app.api.v1.utils.add_thumbnail_url", side_effect=_thumbnail_url),
        patch("app.api.v1.utils._get_thumbnail_asset_url", new=AsyncMock()) as get_thumb,
        patch(
            "app.services.citation_service.CitationService.get_all_citations",
            return_value={"apa": "APA", "mla": "MLA", "chicago": "Chicago"},
        ),
        patch(
            "app.services.viewer_service.ViewerService.get_viewer_attributes",
            return_value={"ui_viewer_protocol": "iiif"},
        ),
        patch(
            "app.services.download_service.DownloadService.get_download_options_with_bridge_asset_downloads",
            new=AsyncMock(
                return_value=[{"label": "Original", "url": "https://example.edu/file.zip"}]
            ),
        ) as downloads,
        patch("app.services.link_service.LinkService.get_links", return_value={}),
        patch(
            "app.services.relationship_service.RelationshipService.get_resource_relationships",
            new=relationship_service,
        ),
    ):
        resource = await presenter.present_full(
            {
                "id": "res-1",
                "dct_title_s": "Search Result",
                "schema_provider_s": "Example University",
            },
            apply_field_mapping=False,
            include_similar_items=False,
            hydration=ResourceHydrationContext(
                distribution_context=_distribution_context(),
                bridge_asset_download_rows=bridge_download_rows,
                ui_relationships={"member_of": []},
                allmaps_attributes={},
                data_dictionaries_payload=[],
                licensed_accesses_payload=[],
                thumbnail_asset_url=None,
            ),
        )

    get_thumb.assert_not_awaited()
    relationship_service.assert_not_awaited()
    downloads.assert_awaited_once_with(bridge_download_rows)
    assert resource == {
        "type": "resource",
        "id": "res-1",
        "attributes": {
            "ogm": {
                "id": "res-1",
                "dct_title_s": "Search Result",
                "dct_references_s": '{"http://schema.org/url": "https://example.edu/catalog/res-1"}',
                "schema_provider_s": "Example University",
            },
        },
        "meta": {
            "@context": "https://gin.btaa.org/ld/contexts/ogm-aardvark-btaa.context.jsonld",
            "@type": "BtaaAardvarkRecord",
            "ui": {
                "thumbnail_url": "https://images.example.edu/res-1-thumb.jpg",
                "citation": "APA",
                "citations": {"apa": "APA", "mla": "MLA", "chicago": "Chicago"},
                "downloads": [{"label": "Original", "url": "https://example.edu/file.zip"}],
                "links": {},
                "relationships": {"member_of": []},
                "viewer": {"protocol": "iiif", "endpoint": None, "geometry": None},
            },
        },
    }


@pytest.mark.asyncio
async def test_resource_presenter_homepage_profile_contract_snapshot():
    presenter = ResourcePresenter(session=None)

    with (
        patch("app.api.v1.utils.add_thumbnail_url", side_effect=_thumbnail_url),
        patch("app.api.v1.utils._get_thumbnail_asset_url", new=AsyncMock()) as get_thumb,
        patch(
            "app.services.viewer_service.ViewerService.get_viewer_attributes",
            return_value={
                "ui_viewer_protocol": "external",
                "ui_viewer_endpoint": "https://example.edu",
            },
        ),
    ):
        resource = await presenter.present_homepage(
            {
                "id": "res-1",
                "dct_title_s": "Homepage Resource",
                "schema_provider_s": "Example University",
                "b1g_code_s": "B1G-001",
            },
            apply_field_mapping=False,
            hydration=ResourceHydrationContext(
                distribution_context=_distribution_context(),
                allmaps_attributes={"manifest_url": "https://example.edu/manifest.json"},
                thumbnail_asset_url=None,
            ),
        )

    get_thumb.assert_not_awaited()
    assert resource == {
        "type": "resource",
        "id": "res-1",
        "attributes": {
            "ogm": {
                "id": "res-1",
                "dct_title_s": "Homepage Resource",
                "schema_provider_s": "Example University",
            },
            "b1g": {"b1g_code_s": "B1G-001"},
        },
        "meta": {
            "@context": "https://gin.btaa.org/ld/contexts/ogm-aardvark-btaa.context.jsonld",
            "@type": "BtaaAardvarkRecord",
            "ui": {
                "thumbnail_url": "https://images.example.edu/res-1-thumb.jpg",
                "viewer": {
                    "protocol": "external",
                    "endpoint": "https://example.edu",
                    "geometry": None,
                },
                "allmaps": {"manifest_url": "https://example.edu/manifest.json"},
            },
        },
    }
