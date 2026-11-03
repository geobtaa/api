"""Focused OGC query contract tests; no live search or application startup required."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.ogc.endpoints import get_search_service, map_ogc_sort, parse_bbox_to_fq, router
from app.elasticsearch.search import GeoFilterBuilder
from app.services.search_service import SearchService


@pytest.fixture
def ogc_client():
    app = FastAPI()
    app.include_router(router, prefix="/ogc")
    service = AsyncMock()
    service.search.return_value = {
        "meta": {"pages": {"total_count": 0, "total_pages": 0}},
        "data": [],
    }
    app.dependency_overrides[get_search_service] = lambda: service
    with TestClient(app) as client:
        yield client, service


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("title", "title_asc"),
        ("+title", "title_asc"),
        ("-title", "title_desc"),
        ("relevance", "relevance"),
        ("-relevance", "relevance"),
    ],
)
def test_supported_sort_mapping(value, expected):
    assert map_ogc_sort(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "bogus", "modified", "-modified", "dateAccessioned", "title,-modified", "+relevance"],
)
def test_unsupported_sorts_are_not_silently_relevance(value):
    with pytest.raises(HTTPException) as error:
        map_ogc_sort(value)
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "bbox",
    [
        "",
        "garbage",
        "1,2,3",
        "1,2,3,4,5,6",
        "nan,0,1,2",
        "0,0,inf,2",
        "-181,-10,10,10",
        "0,-91,10,10",
        "0,0,181,10",
        "0,0,10,91",
        "0,10,10,0",
        "0,0,0,10",
        "0,0,10,0",
        "180,-10,-180,10",
    ],
)
def test_invalid_bbox_returns_400(bbox):
    with pytest.raises(HTTPException) as error:
        parse_bbox_to_fq(bbox)
    assert error.value.status_code == 400


def test_absent_bbox_does_not_filter():
    assert parse_bbox_to_fq(None) is None


@pytest.mark.parametrize(
    ("bbox", "coordinates"),
    [
        ("-100,40,-90,50", [[-100, 50], [-90, 40]]),
        ("-180,-90,180,90", [[-180, 90], [180, -90]]),
        ("180,-10,-170,10", [[-180, 10], [-170, -10]]),
        ("170,-10,-180,10", [[170, 10], [180, -10]]),
    ],
)
def test_bbox_uses_extent_intersection_without_map_overlap_threshold(bbox, coordinates):
    geo = parse_bbox_to_fq(bbox)["geo"]
    query, overlap_context = GeoFilterBuilder().build(geo)
    assert query == {
        "geo_shape": {
            "dcat_bbox": {
                "shape": {"type": "envelope", "coordinates": coordinates},
                "relation": "intersects",
            }
        }
    }
    assert overlap_context is None


@pytest.mark.parametrize(("west", "east"), [(170, -170), (10, -10)])
def test_antimeridian_bbox_splits_instead_of_reversing_corners(west, east):
    geo = parse_bbox_to_fq(f"{west},-10,{east},10")["geo"]
    query, overlap_context = GeoFilterBuilder().build(geo)
    assert query["bool"]["minimum_should_match"] == 1
    clauses = query["bool"]["should"]
    assert [clause["geo_shape"]["dcat_bbox"]["shape"]["coordinates"] for clause in clauses] == [
        [[west, 10], [180, -10]],
        [[-180, 10], [east, -10]],
    ]
    assert all(clause["geo_shape"]["dcat_bbox"]["relation"] == "intersects" for clause in clauses)
    assert overlap_context is None


@pytest.mark.parametrize(
    "params",
    [
        {"datetime": "2024-01-01T00:00:00Z"},
        {"datetime": ""},
        {"bbox": "invalid"},
        {"sortby": "modified"},
        {"sortby": "title,-relevance"},
        {"ids": "one"},
        {"filter": "title='one'"},
        {"filter-lang": "cql2-text"},
        {"filter-crs": "CRS84"},
        {"bbox-crs": "EPSG:3857"},
        {"unknown": "value"},
        [("sortby", "title"), ("sortby", "-title")],
    ],
)
def test_invalid_or_unsupported_queries_fail_before_search(ogc_client, params):
    client, service = ogc_client
    response = client.get("/ogc/collections/btaa-records/items", params=params)
    assert response.status_code == 400
    service.search.assert_not_awaited()


def test_items_passes_supported_query_to_search(ogc_client):
    client, service = ogc_client
    response = client.get(
        "/ogc/collections/btaa-records/items",
        params={"q": "water", "sortby": "+title", "bbox": "-100,40,-90,50", "limit": 5, "page": 2},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"
    kwargs = service.search.await_args.kwargs
    assert (kwargs["q"], kwargs["sort"], kwargs["limit"], kwargs["page"]) == (
        "water",
        "title_asc",
        5,
        2,
    )
    assert kwargs["include_filters"]["geo"]["field"] == "dcat_bbox"
    assert kwargs["exclude_filters"] == {}


def test_items_with_real_search_service_metadata_and_sparse_records():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/ogc")
    app.dependency_overrides[get_search_service] = SearchService
    with patch("app.services.search_service.search_resources", new_callable=AsyncMock) as search:
        search.return_value = {
            "data": [
                {"id": "first", "attributes": {"dct_title_s": "First"}},
                {
                    "id": "second",
                    "attributes": {
                        "dct_title_s": "Second",
                        "dct_description_sm": [],
                        "gbl_resourceClass_sm": None,
                        "gbl_resourceType_sm": None,
                        "dct_spatial_sm": None,
                        "dct_subject_sm": None,
                    },
                },
            ],
            "meta": {"pages": {"total_count": 7, "total_pages": 4}},
            "queryTime": {"elasticsearch": "12ms"},
        }
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/ogc/collections/btaa-records/items", params={"q": "water=a&b", "limit": 2}
            )
    assert response.status_code == 200
    body = response.json()
    assert (body["numberMatched"], body["numberReturned"]) == (7, 2)
    assert body["features"][1]["properties"]["description"] is None
    assert body["features"][1]["properties"]["resourceClass"] == []
    assert "next" in {link["rel"] for link in body["links"]}
    assert body["timeStamp"].endswith("Z")
    assert search.await_args.kwargs["query"] == "water=a&b"


def test_detail_projects_native_nested_shape(ogc_client):
    client, service = ogc_client
    service.get_resource.return_value = {
        "data": {
            "id": "native",
            "attributes": {
                "ogm": {"dct_title_s": "Native item"},
                "b1g": {"b1g_dateAccessioned_s": "2024-01-01"},
            },
            "meta": {"ui": {"viewer": {"geometry": {"type": "Point", "coordinates": [-90, 43]}}}},
        }
    }
    response = client.get("/ogc/collections/btaa-records/items/native")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"
    assert response.json()["properties"]["title"] == "Native item"
    assert response.json()["properties"]["dateAccessioned"] == "2024-01-01"
    assert response.json()["geometry"] == {"type": "Point", "coordinates": [-90, 43]}


@pytest.mark.parametrize("endpoint", ["queryables", "sortables"])
def test_schema_media_type(ogc_client, endpoint):
    client, _service = ogc_client
    response = client.get("/ogc/collections/btaa-records/" + endpoint)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/schema+json"
