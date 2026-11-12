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


def _preview_dialog():
    dialog = MagicMock()
    dialog.results_list.row.return_value = 0
    dialog.current_results = [
        {"attributes": {"ogm": {}}, "meta": {"ui": {"thumbnail_url": "https://example.test/a.png"}}}
    ]
    return dialog


def test_preview_clears_image_after_download_failure():
    dialog = _preview_dialog()
    dialog.api_client.get_thumbnail.side_effect = OSError("unavailable")

    GeodataSearchDialog.show_preview(dialog, MagicMock())

    dialog.preview_image.clear.assert_called_once()


def test_preview_does_not_swallow_keyboard_interrupt():
    import pytest

    dialog = _preview_dialog()
    dialog.api_client.get_thumbnail.side_effect = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        GeodataSearchDialog.show_preview(dialog, MagicMock())
    dialog.preview_image.clear.assert_not_called()


def test_layer_references_do_not_swallow_shutdown():
    import pytest

    dialog = _preview_dialog()
    with patch("ui_dialog.json.loads", side_effect=SystemExit(0)):
        with pytest.raises(SystemExit):
            GeodataSearchDialog.load_selected_layer(dialog, MagicMock())


def test_shapefile_cleanup_preserves_error_when_directory_cannot_be_removed():
    dialog = MagicMock()
    with (
        patch("ui_dialog.zipfile.ZipFile", side_effect=OSError("invalid download")),
        patch("shutil.rmtree", side_effect=OSError("directory unavailable")),
    ):
        GeodataSearchDialog.handle_shapefile_download(
            dialog, "download.zip", True, "/unused", "Map", "https://example.test/map.zip", True
        )
    dialog.show_error.assert_called_once_with("Shapefile Error", "invalid download")
