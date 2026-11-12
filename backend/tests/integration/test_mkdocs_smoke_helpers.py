import json

import pytest
import requests

from tests.integration import test_mkdocs_interactive_examples as smoke

BASE_URL = "https://example.test"
RECORD_URL = f"{BASE_URL}/api/v1/resources/b1g_2Lx2SCAOw85E"


def _response(status):
    response = requests.Response()
    response.status_code = status
    response.url = RECORD_URL
    response._content = json.dumps({"detail": "Resource not found"}).encode()
    return response


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/resources/b1g_2Lx2SCAOw85E/viewer?format=json", RECORD_URL),
        ("/api/v1/resources/b1g_2Lx2SCAOw85E", RECORD_URL),
        ("/api/v1/resources", None),
        ("/api/v1/search", None),
    ],
)
def test_record_prerequisite_url(path, expected):
    assert smoke._example_record_url(f"https://docs.example{path}", BASE_URL) == expected


def test_missing_record_reports_once_and_skips_only_dependent_examples(monkeypatch):
    monkeypatch.setenv("MKDOCS_EXAMPLES_BASE_URL", BASE_URL)
    monkeypatch.setattr(
        smoke,
        "EXAMPLE_FILES",
        ["example-2-obtain-resource.html", "example-25-resource-viewer.html"],
    )
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return _response(404)

    monkeypatch.setattr(smoke, "_live_get", get)
    unavailable = smoke._check_example_records(BASE_URL)
    assert calls == [RECORD_URL]
    assert list(unavailable) == [RECORD_URL]
    with pytest.raises(AssertionError, match="is missing \\(404\\)"):
        smoke.test_mkdocs_example_records_exist(unavailable)
    for name in smoke.EXAMPLE_FILES:
        with pytest.raises(pytest.skip.Exception, match="see test_mkdocs_example_records_exist"):
            smoke.test_mkdocs_examples_live_requests(name, unavailable)
    assert calls == [RECORD_URL]

    # Unrelated endpoint checks still execute, even when example data is absent.
    monkeypatch.setattr(
        smoke, "_live_get", lambda url, **kwargs: calls.append(url) or _response(200)
    )
    smoke.test_mkdocs_examples_live_requests("example-29-placeholder-thumbnail.html", unavailable)
    assert calls[-1] == f"{BASE_URL}/api/v1/thumbnails/placeholder"


@pytest.mark.parametrize("status", [200, 403, 429, 500, 302])
def test_record_preflight_preserves_service_failures(monkeypatch, status):
    monkeypatch.setattr(smoke, "EXAMPLE_FILES", ["example-2-obtain-resource.html"])
    monkeypatch.setattr(smoke, "_live_get", lambda *args, **kwargs: _response(status))
    unavailable = smoke._check_example_records(BASE_URL)
    if status == 200:
        assert unavailable == {}
    else:
        assert str(status) in unavailable[RECORD_URL]
        assert "is missing" not in unavailable[RECORD_URL]
        with pytest.raises(AssertionError):
            smoke.test_mkdocs_example_records_exist(unavailable)


def test_record_preflight_reports_connection_failure(monkeypatch):
    monkeypatch.setattr(smoke, "EXAMPLE_FILES", ["example-2-obtain-resource.html"])

    def get(*args, **kwargs):
        raise requests.ConnectionError("Connection refused")

    monkeypatch.setattr(smoke, "_live_get", get)
    unavailable = smoke._check_example_records(BASE_URL)
    assert "Connection refused" in unavailable[RECORD_URL]


def test_existing_record_does_not_hide_broken_subendpoint(monkeypatch):
    monkeypatch.setenv("MKDOCS_EXAMPLES_BASE_URL", BASE_URL)
    monkeypatch.setattr(smoke, "_live_get", lambda *args, **kwargs: _response(404))
    with pytest.raises(AssertionError, match="returned 404"):
        smoke.test_mkdocs_examples_live_requests("example-25-resource-viewer.html", {})
