import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.errors import (
    COMMON_ERROR_RESPONSES,
    REQUEST_ID_HEADER,
    APIErrorResponse,
    RequestIDMiddleware,
    http_exception_handler,
    internal_server_error_response,
    validation_exception_handler,
)
from app.api.v1.endpoint_modules import search as search_module
from app.main import app as main_app

API_ERROR_REF = {"$ref": "#/components/schemas/APIErrorResponse"}


def _assert_error_payload(
    payload: dict,
    *,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    request_id: str | None = None,
):
    assert payload["errors"][0]["status"] == status
    assert payload["errors"][0]["code"] == code
    assert payload["errors"][0]["title"] == title
    if detail is not None:
        assert payload["errors"][0]["detail"] == detail
    if request_id is not None:
        assert payload["errors"][0]["request_id"] == request_id


def test_error_response_contract_serializes_request_id():
    payload = APIErrorResponse(
        errors=[
            {
                "status": 500,
                "code": "internal_server_error",
                "title": "Internal server error",
                "detail": "An unexpected error occurred.",
                "request_id": "req-123",
            }
        ]
    ).model_dump(exclude_none=True)

    assert payload == {
        "errors": [
            {
                "status": 500,
                "code": "internal_server_error",
                "title": "Internal server error",
                "detail": "An unexpected error occurred.",
                "request_id": "req-123",
            }
        ]
    }


def test_unhandled_exceptions_use_public_safe_error_envelope():
    app = FastAPI(responses=COMMON_ERROR_RESPONSES)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("database password secret")

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return internal_server_error_response(request)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom", headers={REQUEST_ID_HEADER: "req-test"})

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "req-test"
    assert response.json() == {
        "errors": [
            {
                "status": 500,
                "code": "internal_server_error",
                "title": "Internal server error",
                "detail": "An unexpected error occurred.",
                "request_id": "req-test",
            }
        ]
    }
    assert "database password secret" not in response.text


def test_http_exceptions_use_public_error_envelope():
    app = FastAPI(responses=COMMON_ERROR_RESPONSES)
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)

    @app.get("/missing")
    async def missing():
        raise HTTPException(status_code=404, detail="Resource not found")

    client = TestClient(app)
    response = client.get("/missing", headers={REQUEST_ID_HEADER: "req-http"})

    assert response.status_code == 404
    assert response.headers[REQUEST_ID_HEADER] == "req-http"
    _assert_error_payload(
        response.json(),
        status=404,
        code="not_found",
        title="Not found",
        detail="Resource not found",
        request_id="req-http",
    )


def test_http_5xx_details_are_sanitized():
    app = FastAPI(responses=COMMON_ERROR_RESPONSES)
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)

    @app.get("/upstream")
    async def upstream():
        raise HTTPException(status_code=503, detail="postgres://secret@localhost/db")

    client = TestClient(app)
    response = client.get("/upstream", headers={REQUEST_ID_HEADER: "req-upstream"})

    assert response.status_code == 503
    _assert_error_payload(
        response.json(),
        status=503,
        code="service_unavailable",
        title="Service unavailable",
        detail="The service is temporarily unavailable.",
        request_id="req-upstream",
    )
    assert "postgres://secret" not in response.text


def test_validation_errors_use_public_error_envelope():
    app = FastAPI(responses=COMMON_ERROR_RESPONSES)
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.get("/items")
    async def items(limit: int = Query(..., ge=1)):
        return {"limit": limit}

    client = TestClient(app)
    response = client.get("/items?limit=0", headers={REQUEST_ID_HEADER: "req-validation"})

    assert response.status_code == 422
    assert response.headers[REQUEST_ID_HEADER] == "req-validation"
    _assert_error_payload(
        response.json(),
        status=422,
        code="validation_error",
        title="Validation error",
        detail="Request validation failed.",
        request_id="req-validation",
    )


@pytest.mark.unit
def test_main_app_adds_request_id_header_to_normal_responses():
    client = TestClient(main_app)
    response = client.get("/api/v1", headers={REQUEST_ID_HEADER: "req-main"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-main"


def test_openapi_documents_public_success_and_error_schemas():
    client = TestClient(main_app)
    schema = client.get("/api/openapi.json").json()

    component_names = schema["components"]["schemas"]
    for component in (
        "APIErrorResponse",
        "APIRootResponse",
        "SearchResponse",
        "SuggestResponse",
        "FacetResponse",
        "ResourceResponse",
        "ResourceCollectionResponse",
        "ResourceCitationResponse",
        "ResourceDownloadsResponse",
        "DataDictionaryListResponse",
        "HomeBlogPostsResponse",
        "MapH3Response",
        "OGCCollectionsResponse",
        "OGCFeatureCollectionResponse",
        "OGMRepoSummariesResponse",
        "MCPInfoResponse",
    ):
        assert component in component_names

    for hidden_prefix in (
        "/api/v1/admin",
        "/api/v1/gazetteers",
        "/api/v1/feedback",
        "/api/v1/slack",
        "/api/v1/turnstile",
        "/api/v1/shapefiles",
    ):
        assert all(not path.startswith(hidden_prefix) for path in schema["paths"])

    expected_success_schemas = {
        ("/api/v1/", "get"): "#/components/schemas/APIRootResponse",
        ("/api/v1/search", "get"): "#/components/schemas/SearchResponse",
        ("/api/v1/search", "post"): "#/components/schemas/SearchResponse",
        ("/api/v1/search/facets/{facet_name}", "get"): "#/components/schemas/FacetResponse",
        ("/api/v1/suggest", "get"): "#/components/schemas/SuggestResponse",
        ("/api/v1/resources/", "get"): "#/components/schemas/ResourceCollectionResponse",
        ("/api/v1/resources/{id}", "get"): "#/components/schemas/ResourceResponse",
        (
            "/api/v1/resources/{id}/citation",
            "get",
        ): "#/components/schemas/ResourceCitationResponse",
        (
            "/api/v1/resources/{id}/citation/json-ld",
            "get",
        ): "#/components/schemas/SchemaOrgCitationResponse",
        (
            "/api/v1/resources/{id}/downloads",
            "get",
        ): "#/components/schemas/ResourceDownloadsResponse",
        (
            "/api/v1/resources/{id}/downloads/generated/{download_type}",
            "get",
        ): "#/components/schemas/GeneratedDownloadResponse",
        (
            "/api/v1/resources/{id}/data-dictionaries",
            "get",
        ): "#/components/schemas/DataDictionaryListResponse",
        ("/api/v1/home/blog-posts", "get"): "#/components/schemas/HomeBlogPostsResponse",
        ("/api/v1/map/h3", "get"): "#/components/schemas/MapH3Response",
        ("/api/v1/ogc/collections", "get"): "#/components/schemas/OGCCollectionsResponse",
        (
            "/api/v1/ogc/collections/btaa-records/items",
            "get",
        ): "#/components/schemas/OGCFeatureCollectionResponse",
        ("/api/v1/ogm/repos", "get"): "#/components/schemas/OGMRepoSummariesResponse",
        ("/api/v1/mcp", "get"): "#/components/schemas/MCPInfoResponse",
    }
    for (path, method), ref in expected_success_schemas.items():
        assert schema["paths"][path][method]["responses"]["200"]["content"]["application/json"][
            "schema"
        ] == {"$ref": ref}

    for path, operations in schema["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        for method, operation in operations.items():
            if method not in {"get", "post"}:
                continue

            responses = operation["responses"]
            for status_code in ("400", "422", "500"):
                assert (
                    responses[status_code]["content"]["application/json"]["schema"] == API_ERROR_REF
                )

            success_content = responses.get("200", {}).get("content", {})
            success_json = success_content.get("application/json")
            if success_json is not None:
                assert success_json.get("schema")
                assert success_json["schema"] != {}
                assert success_json["schema"] not in (
                    {"$ref": "#/components/schemas/GenericObjectResponse"},
                    {"$ref": "#/components/schemas/GenericArrayResponse"},
                    {"$ref": "#/components/schemas/JSONAPIResponse"},
                )


def _build_request(query_string: bytes = b"q=test") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/search",
            "raw_path": b"/api/v1/search",
            "query_string": query_string,
            "headers": [(REQUEST_ID_HEADER.lower().encode(), b"req-search")],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "root_path": "",
        }
    )


@pytest.mark.asyncio
async def test_search_service_errors_use_public_error_contract(monkeypatch):
    request = _build_request()
    request.state.request_id = "req-search"

    class StubSearchService:
        async def search(self, **kwargs):
            return {"error": "Elasticsearch backend secret"}

    monkeypatch.setattr(search_module, "SearchService", StubSearchService)
    monkeypatch.setattr(
        search_module,
        "_get_cached_search_response_core",
        AsyncMock(return_value=(None, "disabled")),
    )

    response = await search_module._handle_search(
        request,
        {
            "q": "test",
            "page": 1,
            "per_page": 10,
            "request_query_params": "q=test",
        },
    )

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "req-search"
    assert json.loads(response.body) == {
        "errors": [
            {
                "status": 500,
                "code": "elasticsearch_search_failed",
                "title": "Search failed",
                "detail": "Elasticsearch search failed.",
                "request_id": "req-search",
            }
        ]
    }
    assert "backend secret" not in response.body.decode()
