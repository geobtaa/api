from unittest.mock import patch

import pytest

from downloader import DataLoader


@pytest.fixture
def temp_output_path(tmp_path):
    return str(tmp_path / "test_download.json")


@patch("requests.get")
def test_downloader_success(mock_get, temp_output_path):
    # Mocking standard successful request
    mock_response = mock_get.return_value
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {"content-length": "12"}
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]

    loader = DataLoader("http://test.com/data.json", temp_output_path)

    # Hook to verify the signals are called
    progress_calls = []
    finished_calls = []

    def on_progress(p):
        progress_calls.append(p)

    def on_finished(path, success):
        finished_calls.append((path, success))

    loader.progress.emit = on_progress
    loader.finished.emit = on_finished

    loader.run()

    mock_get.assert_called_once()
    assert mock_get.call_args[0][0] == "http://test.com/data.json"

    assert len(finished_calls) == 1
    assert finished_calls[0] == (temp_output_path, True)

    with open(temp_output_path, "rb") as f:
        assert f.read() == b"chunk1chunk2"


@patch("requests.get")
def test_downloader_request_error(mock_get, temp_output_path):
    import requests

    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    loader = DataLoader("http://test.com/data.json", temp_output_path)

    finished_calls = []

    def on_finished(path, success):
        finished_calls.append((path, success))

    loader.finished.emit = on_finished
    loader.run()

    assert len(finished_calls) == 1
    assert finished_calls[0] == ("Download failed: Network error", False)
