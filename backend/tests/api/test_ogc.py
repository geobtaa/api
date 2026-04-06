from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ogc_landing_page():
    response = client.get("/api/v1/ogc/")
    assert response.status_code == 200
    data = response.json()
    assert "links" in data
    assert data["title"] == "BTAA Geospatial API - OGC API Records"


def test_ogc_conformance():
    response = client.get("/api/v1/ogc/conformance")
    assert response.status_code == 200
    data = response.json()
    assert "conformsTo" in data
    assert isinstance(data["conformsTo"], list)


def test_ogc_collections():
    response = client.get("/api/v1/ogc/collections")
    assert response.status_code == 200
    data = response.json()
    assert "collections" in data
    assert data["collections"][0]["id"] == "btaa-records"


def test_ogc_collection():
    response = client.get("/api/v1/ogc/collections/btaa-records")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "btaa-records"


def test_ogc_queryables():
    response = client.get("/api/v1/ogc/collections/btaa-records/queryables")
    assert response.status_code == 200
    data = response.json()
    assert data["$schema"] == "https://json-schema.org/draft/2019-09/schema"
    assert "properties" in data


def test_ogc_sortables():
    response = client.get("/api/v1/ogc/collections/btaa-records/sortables")
    assert response.status_code == 200
    data = response.json()
    assert "properties" in data


@patch("app.api.ogc.endpoints.SearchService")
def test_ogc_items(mock_search_service_class):
    mock_service_instance = AsyncMock()
    mock_search_service_class.return_value = mock_service_instance

    mock_service_instance.search.return_value = {
        "meta": {"totalCount": 1, "totalPages": 1},
        "data": [
            {
                "id": "test-123",
                "attributes": {
                    "id": "test-123",
                    "dct_title_s": "Test Item",
                    "gbl_mdModified_dt": "2023-01-01T00:00:00Z",
                },
            }
        ],
    }

    response = client.get("/api/v1/ogc/collections/btaa-records/items?q=test&limit=10&sortby=title")
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    assert data["features"][0]["id"] == "test-123"
    assert data["features"][0]["properties"]["title"] == "Test Item"

    mock_service_instance.search.assert_called_once()
    call_kwargs = mock_service_instance.search.call_args.kwargs
    assert call_kwargs["q"] == "test"
    assert call_kwargs["limit"] == 10


@patch("app.api.ogc.endpoints.SearchService")
def test_ogc_item(mock_search_service_class):
    mock_service_instance = AsyncMock()
    mock_search_service_class.return_value = mock_service_instance

    mock_service_instance.get_resource.return_value = {
        "data": {
            "type": "resource",
            "id": "test-123",
            "attributes": {"id": "test-123", "dct_title_s": "Test Item"},
        }
    }

    response = client.get("/api/v1/ogc/collections/btaa-records/items/test-123")
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "Feature"
    assert data["id"] == "test-123"
    assert data["properties"]["title"] == "Test Item"
    mock_service_instance.get_resource.assert_called_once_with("test-123")
