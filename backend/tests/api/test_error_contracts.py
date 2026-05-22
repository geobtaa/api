import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.errors import (
    COMMON_ERROR_RESPONSES,
    REQUEST_ID_HEADER,
    APIErrorResponse,
    RequestIDMiddleware,
    internal_server_error_response,
)
from app.api.v1.endpoint_modules import search as search_module
from app.main import app as main_app


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


@pytest.mark.unit
def test_main_app_adds_request_id_header_to_normal_responses():
    client = TestClient(main_app)
    response = client.get("/api/v1", headers={REQUEST_ID_HEADER: "req-main"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-main"


def test_openapi_documents_standard_500_error_schema():
    client = TestClient(main_app)
    schema = client.get("/api/openapi.json").json()

    assert "APIErrorResponse" in schema["components"]["schemas"]
    search_get = schema["paths"]["/api/v1/search"]["get"]
    assert search_get["responses"]["500"]["description"] == "Internal server error"
    assert search_get["responses"]["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/APIErrorResponse"
    }


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
