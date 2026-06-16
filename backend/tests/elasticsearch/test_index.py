"""
Tests for Elasticsearch indexing transformations.
"""

import pytest

import app.elasticsearch.index as index_module


@pytest.mark.asyncio
async def test_process_resource_adds_allmaps_overlay_status(monkeypatch):
    async def fake_get_resource_summaries(resource_id):
        return []

    async def fake_get_spatial_facets(resource_id):
        return None

    async def fake_get_allmaps_overlay_status(resource_id):
        return resource_id == "allmaps-map"

    monkeypatch.setattr(
        index_module,
        "get_resource_summaries",
        fake_get_resource_summaries,
    )
    monkeypatch.setattr(index_module, "get_spatial_facets", fake_get_spatial_facets)
    monkeypatch.setattr(
        index_module,
        "get_allmaps_overlay_status",
        fake_get_allmaps_overlay_status,
    )

    indexed = await index_module.process_resource(
        {
            "id": "allmaps-map",
            "dct_title_s": "Annotated map",
            "gbl_indexYear_im": "1929",
        }
    )

    assert indexed["b1g_georeferenced_allmaps_b"] is True


@pytest.mark.asyncio
async def test_process_resource_defaults_missing_suppression_to_false(monkeypatch):
    async def fake_get_resource_summaries(resource_id):
        return []

    async def fake_get_spatial_facets(resource_id):
        return None

    async def fake_get_allmaps_overlay_status(resource_id):
        return False

    monkeypatch.setattr(index_module, "get_resource_summaries", fake_get_resource_summaries)
    monkeypatch.setattr(index_module, "get_spatial_facets", fake_get_spatial_facets)
    monkeypatch.setattr(index_module, "get_allmaps_overlay_status", fake_get_allmaps_overlay_status)

    indexed = await index_module.process_resource(
        {
            "id": "public-map",
            "dct_title_s": "Public map",
            "publication_state": "published",
        }
    )

    assert indexed["publication_state"] == "published"
    assert indexed["gbl_suppressed_b"] is False
