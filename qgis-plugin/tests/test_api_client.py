from unittest.mock import Mock, patch

import pytest

from api_client import BtaaApiClient


@pytest.fixture
def api_client():
    return BtaaApiClient("http://test-api.example.com")


def test_init_sets_base_url():
    client = BtaaApiClient("http://test-api.example.com/")
    assert client.base_url == "http://test-api.example.com"
    assert client.session.verify is False


def test_init_sets_analytics_headers(api_client):
    assert api_client.session.headers["User-Agent"].startswith("BTAA-QGIS-Plugin/")
    assert api_client.session.headers["X-BTAA-Client-Name"] == "qgis-plugin"
    assert api_client.session.headers["X-BTAA-Client-Version"]
    assert api_client.session.headers["X-BTAA-Client-Channel"] == "qgis"


@patch("requests.Session.get")
def test_get_facets(mock_get, api_client):
    mock_response = Mock()
    mock_response.json.return_value = {"facets": {}}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = api_client.get_facets()

    mock_get.assert_called_once_with(
        "http://test-api.example.com/search",
        params={"q": "", "per_page": 1, "include_filters[dct_accessRights_s][]": "Public"},
    )
    assert result == {"facets": {}}


@patch("requests.Session.get")
def test_search_default_public(mock_get, api_client):
    mock_response = Mock()
    mock_response.json.return_value = {"data": []}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = api_client.search({"q": "water"})

    # Ensure Public is added by default when access rights are missing
    mock_get.assert_called_once_with(
        "http://test-api.example.com/search",
        params={"q": "water", "include_filters[dct_accessRights_s][]": "Public"},
    )
    assert result == {"data": []}


@patch("requests.Session.get")
def test_search_with_custom_access_rights(mock_get, api_client):
    mock_response = Mock()
    mock_response.json.return_value = {"data": []}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = api_client.search(
        {"q": "water", "include_filters[dct_accessRights_s][]": "Restricted"}
    )

    # Ensure Public is NOT added if Restricted is present
    mock_get.assert_called_once_with(
        "http://test-api.example.com/search",
        params={"q": "water", "include_filters[dct_accessRights_s][]": "Restricted"},
    )
    assert result == {"data": []}


@patch("requests.Session.get")
def test_get_thumbnail(mock_get, api_client):
    mock_response = Mock()
    mock_response.content = b"image_data"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = api_client.get_thumbnail("http://test-api.example.com/thumb.jpg")

    mock_get.assert_called_once_with("http://test-api.example.com/thumb.jpg")
    assert result == b"image_data"
