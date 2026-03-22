from unittest.mock import MagicMock, patch

from ui_dialog import GeodataSearchDialog


@patch("api_client.BtaaApiClient.get_facets")
def test_ui_dialog_init(mock_get_facets):
    mock_get_facets.return_value = {
        "included": [{"id": "gbl_resourceClass_sm", "attributes": {"items": [["Dataset"]]}}]
    }
    iface = MagicMock()
    # To run init without error, we need to mock QgsSettings maybe?
    # conftest.py already mocks qgis.core
    dialog = GeodataSearchDialog(iface)
    # just initializing it covers a lot of lines
    assert dialog.iface == iface
