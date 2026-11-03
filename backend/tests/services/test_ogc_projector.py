from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app.api.schemas import OGCFeatureCollectionResponse, OGCFeatureResponse
from app.api.v1.presenters import ResourcePresenter
from app.services.ogc_projector import OGCResponseProjector

ITEMS_URL = "https://catalog.example/api/v1/ogc/collections/btaa-records/items"
GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-90, 43], [-89, 43], [-89, 44], [-90, 44], [-90, 43]]],
}


@pytest.fixture(autouse=True)
def public_url_env(monkeypatch):
    monkeypatch.delenv("APPLICATION_URL", raising=False)


@pytest.fixture
def source_record():
    return {
        "id": "record:123",
        "dct_title_s": "An actual record",
        "dct_description_sm": ["Description"],
        "gbl_resourceClass_sm": ["Datasets"],
        "gbl_resourceType_sm": None,
        "dct_spatial_sm": None,
        "dct_subject_sm": [],
        "gbl_mdModified_dt": datetime(2024, 1, 2, tzinfo=timezone.utc),
        "b1g_dateAccessioned_s": "2023-12-01",
        "b1g_publication_state_s": "published",
        "ui_viewer_geometry": deepcopy(GEOMETRY),
    }


def test_flat_search_and_native_detail_have_identical_properties(source_record):
    # Exercise the real presenter used by SearchService.get_resource, not an
    # invented flat detail payload that would hide the ogm/b1g shape mismatch.
    flat = {"id": source_record["id"], "attributes": source_record}
    nested = ResourcePresenter.serialize_jsonapi_resource(source_record)
    assert "ogm" in nested["attributes"]
    assert "b1g" in nested["attributes"]
    search_item = OGCResponseProjector.build_item(ITEMS_URL, flat)
    detail_item = OGCResponseProjector.build_item(ITEMS_URL, nested)
    assert detail_item == search_item
    assert detail_item["properties"]["title"] == "An actual record"
    assert detail_item["properties"]["dateAccessioned"] == "2023-12-01"
    assert detail_item["geometry"] == GEOMETRY
    OGCFeatureResponse.model_validate(detail_item)


@pytest.mark.parametrize("value", [None, [], [None], "", ["A description"]])
def test_nullable_source_fields_do_not_fail_response_validation(value):
    resource = {
        "id": "nullable",
        "attributes": {
            "dct_description_sm": value,
            "gbl_resourceClass_sm": None,
            "gbl_resourceType_sm": None,
            "dct_spatial_sm": None,
            "dct_subject_sm": None,
        },
    }
    item = OGCFeatureResponse.model_validate(OGCResponseProjector.build_item(ITEMS_URL, resource))
    assert item.properties.resourceClass == []
    assert item.properties.resourceType == []
    assert item.properties.spatial == []
    assert item.properties.subject == []
    assert item.properties.id == "nullable"


def test_pagination_uses_real_search_metadata_and_rfc3339_timestamp(source_record):
    # This is SearchService.search / process_response's actual envelope.
    results = {
        "status": "success",
        "queryTime": {"totalResponseTime": "145ms"},
        "meta": {"pages": {"total_count": 5, "total_pages": 3, "current_page": 2}},
        "data": [{"id": "record:123", "attributes": source_record}],
    }
    before = datetime.now(timezone.utc)
    response = OGCResponseProjector.build_items_response(
        ITEMS_URL + "?q=water%20%26%20land%3Dx%2By&limit=2&page=2&sortby=%2Btitle", results, 2, 2
    )
    parsed = OGCFeatureCollectionResponse.model_validate(response)
    assert before <= parsed.timeStamp <= datetime.now(timezone.utc)
    assert parsed.numberMatched == 5
    assert parsed.numberReturned == 1
    links = {link["rel"]: link["href"] for link in response["links"]}
    for rel, page in (("next", "3"), ("prev", "1")):
        assert parse_qs(urlparse(links[rel]).query) == {
            "q": ["water & land=x+y"],
            "limit": ["2"],
            "page": [page],
            "sortby": ["+title"],
        }


@pytest.mark.parametrize("page,total_pages,count", [(1, 0, 0), (1, 1, 1), (3, 3, 5)])
def test_no_next_link_after_last_page(page, total_pages, count):
    response = OGCResponseProjector.build_items_response(
        ITEMS_URL,
        {"meta": {"pages": {"total_count": count, "total_pages": total_pages}}, "data": []},
        page,
        2,
    )
    assert response["numberMatched"] == count
    assert "next" not in {link["rel"] for link in response["links"]}


def test_timestamp_schema_rejects_duration_strings():
    with pytest.raises(ValidationError):
        OGCFeatureCollectionResponse(timeStamp="145ms")


def test_item_links_use_one_api_prefix_and_encoded_ids(monkeypatch):
    monkeypatch.setenv("APPLICATION_URL", "https://catalog.example/api/v1/")
    item = OGCResponseProjector.build_item(
        ITEMS_URL.replace("https://catalog.example", "http://internal:8000"),
        {"id": "record:1?part=a&b", "attributes": {}},
    )
    links = {link["rel"]: link["href"] for link in item["links"]}
    assert links["alternate"] == (
        "https://catalog.example/api/v1/resources/record%3A1%3Fpart%3Da%26b"
    )
    assert links["self"].endswith("/items/record%3A1%3Fpart%3Da%26b")
    assert all(url.startswith("https://catalog.example/") for url in links.values())


def test_discovery_uses_public_origin_and_actual_supported_capabilities(monkeypatch):
    monkeypatch.setenv("APPLICATION_URL", "https://catalog.example")
    url = "http://internal:8000/api/v1/ogc/"
    landing = OGCResponseProjector.build_landing_page(url + "?ignored=value")
    links = {link["rel"]: link["href"] for link in landing["links"]}
    assert links["service-desc"] == "https://catalog.example/api/openapi.json"
    assert links["service-doc"] == "https://catalog.example/api/docs"
    assert links["self"] == "https://catalog.example/api/v1/ogc/"
    collections = OGCResponseProjector.build_collections(url + "collections")
    assert collections["collections"][0]["type"] == "Catalog"
    assert OGCResponseProjector.build_conformance() == {"conformsTo": []}
    assert OGCResponseProjector.build_queryables(url)["properties"] == {}
    assert set(OGCResponseProjector.build_sortables(url)["properties"]) == {"title", "relevance"}


@pytest.mark.parametrize(
    "geometry",
    [
        None,
        {},
        {"type": "Point", "coordinates": [float("nan"), 1]},
        {"type": "Point", "coordinates": [1]},
        {"type": "Point", "coordinates": [200, 10]},
        {"type": "Polygon", "coordinates": [1, 2]},
        {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0]]]},
    ],
)
def test_unusable_geometry_remains_null(geometry):
    response = OGCResponseProjector.build_item(
        ITEMS_URL, {"id": "1", "attributes": {"ui_viewer_geometry": geometry}}
    )
    assert response["geometry"] is None


def test_geometry_type_normalized_without_mutating_source():
    geometry = {"type": "Multilinestring", "coordinates": [[[1, 2], [3, 4]]]}
    response = OGCResponseProjector.build_item(
        ITEMS_URL, {"id": "1", "attributes": {"ui_viewer_geometry": geometry}}
    )
    assert response["geometry"]["type"] == "MultiLineString"
    assert geometry["type"] == "Multilinestring"


def test_url_path_parsing_does_not_split_hostname():
    url = "https://ogc.example/api/v1/ogc/collections/btaa-records/items"
    item = OGCResponseProjector.build_item(url, {"id": "1", "attributes": {}})
    assert item["links"][0]["href"] == url + "/1"
    collection = OGCResponseProjector.build_collection(
        "https://collections.example/api/v1/ogc/collections/btaa-records", "btaa-records"
    )
    assert collection["links"][0]["href"].startswith("https://collections.example/")
