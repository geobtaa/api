"""Executable URL and OpenAPI guarantees independent of the database."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_api import make_settings

from app.api.dependencies import engine
from app.api.v1 import resources
from app.auth import Actor
from app.domain import DomainError
from app.main import create_app
from app.url_ids import RESERVED, decode_id, encode_id

IDS = [
    "normal-id_123",
    "editor/test",
    "editor/relationships",
    "editor/metadata",
    "facets/field",
    "a?b#c",
    "100%done",
    "a%2Fb",
    "white space",
    "é/地图",
    ".",
    "..",
    "../relative",
    "~escaped",
    "/leading",
    "trailing/",
    "new",
    "a" * 512,
    "界" * 512,
    *sorted(RESERVED),
]


@pytest.mark.parametrize("identifier", IDS)
def test_url_key_is_lossless_and_one_canonical_segment(identifier):
    key = encode_id(identifier)
    assert "/" not in key and "?" not in key and "#" not in key
    assert key not in RESERVED and key not in {".", ".."}
    assert decode_id(key) == identifier


@pytest.mark.parametrize(
    "key", ["", "~", "~?", "~_w", "~YQ==", "~YQ", "~IA", "~AA", "~Y", "new", "a/b", "x" * 513]
)
def test_invalid_or_noncanonical_keys_are_rejected(key):
    with pytest.raises(ValueError):
        decode_id(key)


async def staff(_):
    return Actor("staff", "user", "Staff", None, frozenset({"resources:read"}))


@pytest.mark.parametrize("identifier", IDS)
def test_member_and_nested_reads_resolve_the_same_original_id(identifier, monkeypatch):
    seen = []

    async def record(database, actor, resource_id):
        seen.append(resource_id)
        raise DomainError(404, "not_found", "Missing or inaccessible Resource")

    async def relationships(database, actor, resource_id, offset, limit):
        return await record(database, actor, resource_id)

    monkeypatch.setattr(resources.service, "detail", record)
    monkeypatch.setattr(resources.resource_preview, "record", record)
    monkeypatch.setattr(resources.relationships, "page", relationships)
    app = create_app(settings=make_settings(), authenticator=staff)
    app.dependency_overrides[engine] = lambda: object()
    with TestClient(app) as client:
        path = "/api/v1/admin/resources/" + encode_id(identifier)
        for suffix in ["", "/metadata", "/relationships"]:
            response = client.get(path + suffix)
            assert response.status_code == 404, response.text
            assert response.json()["detail"]["code"] == "not_found"
    assert seen == [identifier] * 3


def test_openapi_is_typed_resourceful_and_explicit_about_security():
    schema = create_app(settings=make_settings()).openapi()
    paths = schema["paths"]
    assert "/api/v1/admin/resources/{resource_id}" in paths
    assert set(paths["/api/v1/admin/session"]) == {"get", "post", "delete"}
    assert not any("/detail" in path or "/projections/" in path for path in paths)
    assert not any("projection" in name.lower() for name in schema["components"]["schemas"])
    assert schema["components"]["securitySchemes"]["SessionCookie"]["in"] == "cookie"
    operations = [op for methods in paths.values() for op in methods.values()]
    ids = [op["operationId"] for op in operations]
    assert len(ids) == len(set(ids))
    for op in operations:
        assert op["summary"] not in {"Index", "Detail", "Contract", "Commit"}
        for status, response in op["responses"].items():
            if status.startswith("2"):
                assert response.get("content"), op["operationId"]
                assert all(item.get("schema") for item in response["content"].values()), op[
                    "operationId"
                ]
        for parameter in op.get("parameters", []):
            if parameter["name"].lower() == "x-geomg-request":
                assert parameter["required"] and parameter["schema"]["const"] == "1"
    assert paths["/api/v1/admin/workflow-catalog"]["get"]["security"] == [{"SessionCookie": []}]
    create = paths["/api/v1/admin/resources"]["post"]
    assert create["security"] == [{"SessionCookie": []}]
    assert "Location" in create["responses"]["201"]["headers"]
    resource = paths["/api/v1/admin/resources/{resource_id}"]
    assert resource["get"]["security"] == [{"SessionCookie": []}]
    assert {p["name"] for p in resource["get"]["parameters"]} == {"resource_id"}
    assert resource["patch"]["responses"]["409"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("ErrorResponse")
    for name in ["template", "export"]:
        assert set(
            paths["/api/v1/admin/resources/csv/" + name]["get"]["responses"]["200"]["content"]
        ) == {"text/csv"}
    assert "security" not in paths["/api/v1/admin/identity/providers"]["get"]
    for domain in ["resources", "sources", "sets", "jobs", "tasks", "workflows"]:
        assert "/api/v1/admin/contracts/" + domain in paths


def test_production_has_no_development_routes_or_projection():
    app = create_app(settings=replace(make_settings(), app_env="production"))
    paths = app.openapi()["paths"]
    assert "/api/v1/admin/resource-fixtures" not in paths
    assert "/api/v1/admin/resources/bridge/batches" not in paths
    with TestClient(app) as client:
        for path in ["/api/v1/admin/projections/sources", "/api/v1/admin/resource-fixtures"]:
            assert client.get(path).status_code == 404
        assert client.post("/api/v1/admin/resources/bridge/batches").status_code == 405


def test_authentication_validation_and_http_errors_share_an_envelope():
    app = create_app(settings=make_settings())
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/resources/example")
        assert response.status_code == 401
        assert response.json() == {
            "detail": {
                "code": "unauthenticated",
                "message": "Authentication required",
                "errors": [],
            }
        }
        invalid = client.post("/api/v1/admin/session", json={})
        assert invalid.status_code == 422
        assert invalid.json()["detail"]["code"] == "validation_error"
        assert invalid.json()["detail"]["errors"][0]["loc"] == ["header", "x-geomg-request"]
        assert "input" not in invalid.text
        unknown = client.get("/api/v1/unknown")
        assert unknown.json()["detail"]["code"] == "not_found"


def test_internal_failures_do_not_expose_details(monkeypatch):
    async def fail(*args):
        raise RuntimeError("PRIVATE database details")

    monkeypatch.setattr(resources.service, "detail", fail)
    app = create_app(settings=make_settings(), authenticator=staff)
    app.dependency_overrides[engine] = lambda: object()
    with TestClient(app, raise_server_exceptions=False) as client:
        result = client.get("/api/v1/admin/resources/example")
        assert result.status_code == 500
        assert result.json() == {
            "detail": {
                "code": "internal_error",
                "message": "The request could not be completed",
                "errors": [],
            }
        }
        assert "PRIVATE" not in result.text


def test_swagger_ordering_preserves_proxy_paths_and_route_precedence():
    app = create_app(settings=make_settings())
    with TestClient(app, root_path="/geomg") as client:
        docs = client.get("/api/docs")
        assert docs.status_code == 200
        assert "url: '/geomg/api/openapi.json'" in docs.text
        assert '"operationsSorter": (a, b) =>' in docs.text
        paths = list(client.get("/api/openapi.json").json()["paths"])
        assert paths.index("/api/v1/admin/resources/facets") < paths.index(
            "/api/v1/admin/resources/{resource_id}"
        )
