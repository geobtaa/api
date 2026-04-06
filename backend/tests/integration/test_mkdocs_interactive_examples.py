import os
import re
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
ENDPOINTS_DOC = REPO_ROOT / "mkdocs" / "docs" / "specification" / "endpoints.md"
EXAMPLES_DIR = REPO_ROOT / "mkdocs" / "docs" / "includes" / "examples"


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


def _normalize_api_path(path: str) -> str:
    if path.startswith("/api/v1/"):
        return path
    if path == "/api/v1":
        return "/api/v1/"
    if path.startswith("/"):
        return f"/api/v1{path}"
    return f"/api/v1/{path}"


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


@pytest.mark.parametrize("example_name", EXAMPLE_FILES)
def test_mkdocs_examples_live_requests(example_name: str):
    """
    Optional live integration test for interactive examples.

    Set MKDOCS_EXAMPLES_BASE_URL to run, e.g.:
    MKDOCS_EXAMPLES_BASE_URL=http://localhost:8000 \
    python -m pytest backend/tests/integration/test_mkdocs_interactive_examples.py -q
    """
    base_url = os.getenv("MKDOCS_EXAMPLES_BASE_URL")
    if not base_url:
        pytest.skip("Set MKDOCS_EXAMPLES_BASE_URL to enable live docs-example tests")

    content = (EXAMPLES_DIR / example_name).read_text(encoding="utf-8")
    raw_path = _extract_first_requests_path(content)
    assert raw_path is not None, f"Unable to parse request path in {example_name}"

    path = _render_path(_normalize_api_path(raw_path))
    response = requests.get(
        f"{base_url.rstrip('/')}{path}",
        timeout=30,
        allow_redirects=False,
    )

    # Core smoke check: examples should never hit server errors.
    assert response.status_code < 500, (
        f"{example_name} endpoint returned {response.status_code} for {path}"
    )

    # Per-example shape checks for the responses our interactive output parsing depends on.
    if example_name == "example-12-list-resources.html":
        data = response.json()
        meta = data.get("meta", {})
        assert "totalCount" in meta and "currentPage" in meta and "perPage" in meta

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
