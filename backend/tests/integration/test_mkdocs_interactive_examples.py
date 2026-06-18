import os
import re
import sys
import time
from contextlib import redirect_stdout
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit, urlunsplit

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
ENDPOINTS_DOC = REPO_ROOT / "mkdocs" / "docs" / "specification" / "endpoints.md"
EXAMPLES_DIR = REPO_ROOT / "mkdocs" / "docs" / "includes" / "examples"
PRODUCTION_API_BASE_URL = "https://lib-geoportal-prd-web-01.oit.umn.edu"
URBAN_BASE_LAYERS_COLLECTION_ID = "b1g_urbanBaseLayers"
DISPLAY_NOTE_PREFIX_REGRESSION_RESOURCE_ID = "b1g_2Lx2SCAOw85E"
DISPLAY_NOTE_PREFIX_REGRESSION_BODY = (
    "This dataset is a historical version held by the BTAA-GIN. "
    "For the most current layer, consult Open Data Minneapolis"
)
_LAST_LIVE_REQUEST_AT: float | None = None
LIVE_REQUEST_ATTEMPTS = 3


def _production_smoke_enabled() -> bool:
    return os.getenv("RUN_PRODUCTION_SMOKE_TESTS", "").strip().lower() in {"1", "true", "yes", "on"}


def _live_request_interval_seconds() -> float:
    return float(os.getenv("PRODUCTION_SMOKE_MIN_REQUEST_INTERVAL_SECONDS", "0"))


def _pace_live_request() -> None:
    global _LAST_LIVE_REQUEST_AT

    interval = _live_request_interval_seconds()
    if interval <= 0:
        return

    now = time.monotonic()
    if _LAST_LIVE_REQUEST_AT is not None:
        elapsed = now - _LAST_LIVE_REQUEST_AT
        if elapsed < interval:
            time.sleep(interval - elapsed)
    _LAST_LIVE_REQUEST_AT = time.monotonic()


def _live_get(url: str, **kwargs) -> requests.Response:
    last_error: requests.RequestException | None = None
    for attempt in range(1, LIVE_REQUEST_ATTEMPTS + 1):
        try:
            _pace_live_request()
            return requests.get(url, **kwargs)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == LIVE_REQUEST_ATTEMPTS:
                break
            time.sleep(min(2 * attempt, 5))

    raise last_error or RuntimeError(f"Unable to request {url}")


@dataclass(frozen=True)
class CapturedRequest:
    url: str
    params: dict | None
    kwargs: dict


class _ExampleResponse:
    status_code = 200
    text = "<html><body>Example response</body></html>"
    headers = {
        "Content-Type": "application/json",
        "Location": "https://example.test/thumbnail.png",
    }
    content = b"example-image"

    def __init__(self, url: str):
        self.url = url

    def json(self) -> dict:
        if re.search(r"/resources/[^/]+$", self.url):
            return {
                "data": {
                    "id": "example-resource",
                    "attributes": {
                        "dct_title_s": "Example title",
                        "dct_description_sm": ["Example description"],
                        "dct_references_s": "{}",
                    },
                }
            }
        if self.url.endswith("/links"):
            return {"Web Services": [{"label": "Example link", "url": "https://example.test"}]}

        return {
            "capabilities": {"tools": []},
            "collections": [],
            "citation": "Example citation",
            "data": [
                {
                    "id": "example-resource",
                    "attributes": {
                        "dct_title_s": "Example title",
                        "dct_description_sm": ["Example description"],
                        "ogm": {
                            "dct_title_s": "Example title",
                            "dct_subject_sm": ["Example subject"],
                        },
                        "value": "Example facet",
                        "hits": 1,
                    },
                    "meta": {
                        "ui": {
                            "thumbnail_url": "https://example.test/thumbnail.png",
                        },
                    },
                }
            ],
            "distributions": [],
            "downloads": [],
            "links": {},
            "meta": {"totalCount": 1, "currentPage": 1, "perPage": 10},
            "ogm": {
                "dct_title_s": "Example title",
                "dct_description_sm": ["Example description"],
            },
            "spatial_facets": {},
            "suggestions": [{"text": "water"}],
            "viewer": {"protocol": "geo_json", "endpoint": "https://example.test/viewer"},
        }


class _RequestsRecorder(ModuleType):
    def __init__(self):
        super().__init__("requests")
        self.calls: list[CapturedRequest] = []

    def get(self, url: str, **kwargs) -> _ExampleResponse:
        self.calls.append(
            CapturedRequest(
                url=url,
                params=kwargs.pop("params", None),
                kwargs=kwargs,
            )
        )
        return _ExampleResponse(url)


class _FakeWritableFile:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def write(self, content: bytes) -> int:
        return len(content)


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in {"script", "style"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str):
        if tag.lower() in {"script", "style"} and self._hidden_depth > 0:
            self._hidden_depth -= 1

    def handle_data(self, data: str):
        if self._hidden_depth == 0 and data.strip():
            self.parts.append(data.strip())


def _visible_text_from_html(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


def _visible_url_hosts(text: str) -> set[str]:
    hosts = set()
    for token in text.split():
        candidate = token.strip(".,;:!?)('\"[]{}")
        parsed = urlsplit(candidate)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            hosts.add(parsed.hostname)
    return hosts


def _is_frontend_turnstile_gate(response: requests.Response) -> bool:
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "text/html" not in content_type:
        return False

    visible_text = _visible_text_from_html(response.text)
    return (
        "Browser verification" in visible_text
        and "Continue to the BTAA Geoportal" in visible_text
        and "Complete the verification check to continue to the BTAA Geoportal" in visible_text
    )


def _included_example_files() -> list[str]:
    content = ENDPOINTS_DOC.read_text(encoding="utf-8")
    return re.findall(r'includes/examples/(example-\d+[^"]+\.html)', content)


def _extract_first_requests_path(example_content: str) -> str | None:
    # Match both: requests.get(f"{BASE_URL}/path...") and requests.get(f"{API_ROOT_EXAMPLE_URL}")
    match = re.search(r'requests\.get\(\s*f?"\{[A-Z_]+\}([^"]*)"', example_content)
    if match:
        return match.group(1) or "/"

    # Fallback for requests.get(API_ROOT_EXAMPLE_URL)
    if "requests.get(API_ROOT_EXAMPLE_URL)" in example_content:
        return "/api/v1/"

    return None


def _extract_visible_python_snippet(example_content: str) -> str:
    match = re.search(
        r'<pre><code[^>]*class="language-python"[^>]*>(.*?)</code></pre>',
        example_content,
        flags=re.DOTALL,
    )
    assert match is not None, "Missing visible Python snippet"
    return unescape(match.group(1))


def _capture_example_requests(example_name: str) -> list[CapturedRequest]:
    snippet = _extract_visible_python_snippet(
        (EXAMPLES_DIR / example_name).read_text(encoding="utf-8")
    )
    recorder = _RequestsRecorder()
    original_requests = sys.modules.get("requests")
    sys.modules["requests"] = recorder
    try:
        with redirect_stdout(StringIO()):
            exec(
                compile(snippet, example_name, "exec"),
                {
                    "__name__": "__mkdocs_example__",
                    "open": lambda *args, **kwargs: _FakeWritableFile(),
                },
            )
    finally:
        if original_requests is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = original_requests
    return recorder.calls


def _normalize_api_path(path: str) -> str:
    if path.startswith("/api/v1/"):
        return path
    if path == "/api/v1":
        return "/api/v1/"
    if path.startswith("/"):
        return f"/api/v1{path}"
    return f"/api/v1/{path}"


def _url_against_base(url: str, base_url: str) -> str:
    parsed_url = urlsplit(url)
    parsed_base = urlsplit(base_url.rstrip("/"))
    path = parsed_url.path or "/"
    if not path.startswith("/api/v1"):
        path = _normalize_api_path(path)
    return urlunsplit(
        (
            parsed_base.scheme,
            parsed_base.netloc,
            path,
            parsed_url.query,
            parsed_url.fragment,
        )
    )


def _render_path(path: str) -> str:
    resource_id = os.getenv("MKDOCS_EXAMPLES_RESOURCE_ID", "ark28722-s7vs38")
    record_id = os.getenv("MKDOCS_EXAMPLES_RECORD_ID", "stanford-yc270hg1347")
    facet_name = os.getenv("MKDOCS_EXAMPLES_FACET_NAME", "gbl_resourceClass_sm")

    return (
        path.replace("{resource_id}", resource_id)
        .replace("{id}", resource_id)
        .replace("{recordId}", record_id)
        .replace("{record_id}", record_id)
        .replace("{facet_name}", facet_name)
    )


EXAMPLE_FILES = _included_example_files()


def _assert_json_api_search_response(data: dict) -> None:
    assert "meta" in data, "Search response is missing meta"
    assert "data" in data, "Search response is missing data"
    assert isinstance(data["data"], list), "Search data must be a list"
    assert "totalCount" in data["meta"], "Search meta is missing totalCount"


def _assert_not_turnstile_blocked(response: requests.Response, context: str) -> None:
    assert response.status_code != 403, (
        f"{context} was blocked with 403. Body: {response.text[:300]}"
    )
    assert response.headers.get("X-Turnstile-Required") != "true", (
        f"{context} unexpectedly required Turnstile"
    )
    try:
        payload = response.json()
    except ValueError:
        return
    assert payload.get("error") != "turnstile_required", f"{context} was blocked by Turnstile"


def _assert_not_rate_limited(response: requests.Response, context: str) -> None:
    assert response.status_code != 429, (
        f"{context} was rate limited. Increase PRODUCTION_SMOKE_MIN_REQUEST_INTERVAL_SECONDS. "
        f"Body: {response.text[:300]}"
    )


@pytest.mark.parametrize("example_name", EXAMPLE_FILES)
def test_mkdocs_examples_have_required_structure(example_name: str):
    """Validate all interactive examples referenced by endpoints.md are runnable."""
    path = EXAMPLES_DIR / example_name
    assert path.exists(), f"Missing included example file: {example_name}"

    content = path.read_text(encoding="utf-8")
    assert '<script type="py">' in content, f"Missing PyScript block in {example_name}"
    assert "requests.get(" in content, f"Missing requests usage in {example_name}"
    assert "run-btn-" in content, f"Missing run button in {example_name}"

    request_path = _extract_first_requests_path(content)
    assert request_path is not None, f"Unable to parse request path in {example_name}"

    captured_requests = _capture_example_requests(example_name)
    assert captured_requests, f"Unable to capture requests.get calls in {example_name}"


@pytest.mark.parametrize("example_name", EXAMPLE_FILES)
def test_mkdocs_examples_live_requests(example_name: str):
    """
    Optional live integration test for interactive examples.

    Set MKDOCS_EXAMPLES_BASE_URL to run, e.g.:
    MKDOCS_EXAMPLES_BASE_URL=http://localhost:8000 \
    python -m pytest backend/tests/integration/test_mkdocs_interactive_examples.py -q
    """
    if not _production_smoke_enabled() and not os.getenv("MKDOCS_EXAMPLES_BASE_URL"):
        pytest.skip("Set RUN_PRODUCTION_SMOKE_TESTS=true to enable live docs-example tests")

    base_url = os.getenv("MKDOCS_EXAMPLES_BASE_URL", PRODUCTION_API_BASE_URL)
    captured_requests = _capture_example_requests(example_name)
    assert captured_requests, f"Unable to capture requests.get calls in {example_name}"

    for index, captured in enumerate(captured_requests, start=1):
        url = _url_against_base(captured.url, base_url)
        kwargs = dict(captured.kwargs)
        kwargs["timeout"] = float(os.getenv("MKDOCS_EXAMPLES_TIMEOUT_SECONDS", "30"))
        kwargs.setdefault("allow_redirects", False)
        response = _live_get(url, params=captured.params, **kwargs)
        context = f"{example_name} request #{index} {response.url}"

        _assert_not_turnstile_blocked(response, context)
        _assert_not_rate_limited(response, context)
        assert response.status_code < 500, (
            f"{context} returned {response.status_code}. Body: {response.text[:300]}"
        )
        assert response.status_code != 404, f"{context} returned 404"

    # Per-example shape checks for the responses our interactive output parsing depends on.
    if example_name == "example-12-list-resources.html":
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    elif example_name == "example-13-resource-distributions.html":
        data = response.json()
        assert "distributions" in data
        assert isinstance(data["distributions"], list)

    elif example_name == "example-15-resource-metadata.html":
        data = response.json()
        assert "ogm" in data
        assert isinstance(data["ogm"], dict)

    elif example_name == "example-24-resource-thumbnail.html":
        assert response.status_code in {200, 302, 307, 308}
        location = response.headers.get("Location")
        content_type = (response.headers.get("Content-Type") or "").lower()
        assert location or content_type.startswith("image/")

    elif example_name == "example-25-resource-viewer.html":
        data = response.json()
        viewer = data.get("viewer", {})
        assert "protocol" in viewer and "endpoint" in viewer

    elif example_name == "example-26-facet-pagination.html":
        data = response.json()
        meta = data.get("meta", {})
        assert "totalCount" in meta and "currentPage" in meta and "perPage" in meta
        for item in data.get("data", [])[:3]:
            attrs = item.get("attributes", {})
            assert "value" in attrs and "hits" in attrs

    elif example_name == "example-31-ogc-collections.html":
        data = response.json()
        assert "collections" in data
        assert isinstance(data["collections"], list)

    elif example_name == "example-32-mcp-endpoint.html":
        data = response.json()
        assert "capabilities" in data and "tools" in data.get("capabilities", {})


@pytest.mark.network
def test_urban_base_layers_gallery_keeps_thumbnails():
    if not _production_smoke_enabled() and not os.getenv("MKDOCS_EXAMPLES_BASE_URL"):
        pytest.skip("Set RUN_PRODUCTION_SMOKE_TESTS=true to enable Urban Base Layers smoke test")

    base_url = os.getenv("MKDOCS_EXAMPLES_BASE_URL", PRODUCTION_API_BASE_URL).rstrip("/")
    response = _live_get(
        f"{base_url}/api/v1/search",
        params={
            "include_filters[pcdm_memberOf_sm][]": URBAN_BASE_LAYERS_COLLECTION_ID,
            "view": "gallery",
            "per_page": 20,
        },
        timeout=float(os.getenv("MKDOCS_EXAMPLES_TIMEOUT_SECONDS", "30")),
    )
    _assert_not_turnstile_blocked(response, response.url)
    _assert_not_rate_limited(response, response.url)
    assert response.status_code == 200, response.text[:300]

    payload = response.json()
    _assert_json_api_search_response(payload)
    assert payload["meta"]["totalCount"] >= 20
    assert len(payload["data"]) == 20

    missing_thumbnail_ids = []
    placeholder_thumbnail_ids = []
    thumbnail_urls = []
    for item in payload["data"]:
        item_id = item["id"]
        thumbnail_url = item.get("meta", {}).get("ui", {}).get("thumbnail_url")
        if not thumbnail_url:
            missing_thumbnail_ids.append(item_id)
            continue
        if "placeholder" in thumbnail_url.lower():
            placeholder_thumbnail_ids.append(item_id)
        thumbnail_urls.append((item_id, thumbnail_url))

    assert not missing_thumbnail_ids, (
        "Urban Base Layers records missing gallery thumbnail_url: "
        + ", ".join(missing_thumbnail_ids)
    )
    assert not placeholder_thumbnail_ids, (
        "Urban Base Layers records fell back to placeholder thumbnails: "
        + ", ".join(placeholder_thumbnail_ids)
    )

    sample_size = int(os.getenv("URBAN_BASE_LAYERS_THUMBNAIL_SAMPLE_SIZE", "5"))
    for item_id, thumbnail_url in thumbnail_urls[:sample_size]:
        thumbnail_response = _live_get(
            thumbnail_url,
            timeout=float(os.getenv("MKDOCS_EXAMPLES_TIMEOUT_SECONDS", "30")),
            allow_redirects=True,
        )
        _assert_not_rate_limited(thumbnail_response, thumbnail_url)
        assert thumbnail_response.status_code == 200, (
            f"{item_id} thumbnail returned {thumbnail_response.status_code}: {thumbnail_url}"
        )
        content_type = (thumbnail_response.headers.get("Content-Type") or "").lower()
        assert content_type.startswith("image/"), (
            f"{item_id} thumbnail did not return image content: "
            f"{content_type or 'missing Content-Type'} from {thumbnail_url}"
        )
        assert thumbnail_response.content, f"{item_id} thumbnail response was empty"


@pytest.mark.network
def test_resource_page_hides_display_note_style_prefixes():
    if not _production_smoke_enabled() and not os.getenv("MKDOCS_EXAMPLES_BASE_URL"):
        pytest.skip("Set RUN_PRODUCTION_SMOKE_TESTS=true to enable resource page smoke test")

    base_url = os.getenv("MKDOCS_EXAMPLES_BASE_URL", PRODUCTION_API_BASE_URL).rstrip("/")
    resource_url = f"{base_url}/resources/{DISPLAY_NOTE_PREFIX_REGRESSION_RESOURCE_ID}"
    response = _live_get(
        resource_url,
        timeout=float(os.getenv("MKDOCS_EXAMPLES_TIMEOUT_SECONDS", "30")),
    )
    if _is_frontend_turnstile_gate(response):
        pytest.skip("Production frontend resource page is behind Turnstile browser verification")

    _assert_not_turnstile_blocked(response, resource_url)
    _assert_not_rate_limited(response, resource_url)
    assert response.status_code == 200, response.text[:300]

    visible_text = _visible_text_from_html(response.text)
    assert DISPLAY_NOTE_PREFIX_REGRESSION_BODY in visible_text
    assert any(host == "opendata.minneapolismn.gov" for host in _visible_url_hosts(visible_text))
    assert f"Warning: {DISPLAY_NOTE_PREFIX_REGRESSION_BODY}" not in visible_text
