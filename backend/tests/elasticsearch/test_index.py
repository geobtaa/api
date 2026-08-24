"""
Tests for Elasticsearch indexing transformations.
"""

import pytest

import app.elasticsearch.index as index_module


def test_process_geometry_indexes_wkt_point():
    assert index_module.process_geometry("POINT(-87.6200 43.0800)") == {
        "type": "Point",
        "coordinates": [-87.62, 43.08],
    }


def test_process_geometry_converts_zero_area_bbox_to_point():
    assert index_module.process_geometry("-87.62,43.08,-87.62,43.08") == {
        "type": "point",
        "coordinates": [-87.62, 43.08],
    }


def test_process_geometry_preserves_near_global_bbox_as_polygon():
    geometry = index_module.process_geometry("-179.999,-80.000,179.999,80.000")

    assert geometry["type"] == "polygon"
    assert geometry["coordinates"] == [
        [
            [-179.999, 80.0],
            [179.999, 80.0],
            [179.999, -80.0],
            [-179.999, -80.0],
            [-179.999, 80.0],
        ]
    ]


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


@pytest.mark.asyncio
async def test_process_resource_derives_index_year_from_date_range(monkeypatch):
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
            "id": "bridge-resource",
            "gbl_indexYear_im": None,
            "gbl_dateRange_drsim": ["2024-2024"],
        }
    )

    assert indexed["gbl_indexYear_im"] == [2024]
    assert indexed["time_period"] == "2020-2024"


@pytest.mark.asyncio
async def test_process_resource_defaults_ogm_repo_to_btaa(monkeypatch):
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
            "id": "btaa-map",
            "dct_title_s": "BTAA map",
            "b1g_adminTags_sm": ["featured"],
        }
    )

    assert indexed["ogm_repo"] == ["btaa"]


@pytest.mark.asyncio
async def test_process_resource_derives_ogm_repo_from_admin_tags(monkeypatch):
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
            "id": "ogm-map",
            "dct_title_s": "OGM map",
            "b1g_adminTags_sm": [
                "ogm_repo:edu.stanford.purl",
                "ogm_repo:edu.stanford.purl",
                "ogm_repo:edu.umn",
            ],
        }
    )

    assert indexed["ogm_repo"] == ["edu.stanford.purl", "edu.umn"]
