from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"


class APIError(BaseModel):
    """Public API error object shared by exception handlers and OpenAPI docs."""

    status: int = Field(..., ge=400, le=599)
    code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    detail: str | None = None
    request_id: str | None = None


class APIErrorResponse(BaseModel):
    errors: list[APIError] = Field(..., min_length=1)


_ERROR_TITLES: dict[int, str] = {
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    422: "Validation error",
    429: "Rate limit exceeded",
    500: "Internal server error",
    502: "Upstream service failed",
    503: "Service unavailable",
}

_ERROR_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
    502: "upstream_service_failed",
    503: "service_unavailable",
}


def _openapi_error_response(description: str) -> dict[str, Any]:
    return {
        "model": APIErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/APIErrorResponse"},
            }
        },
    }


PUBLIC_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _openapi_error_response("Bad request"),
    401: _openapi_error_response("Unauthorized"),
    403: _openapi_error_response("Forbidden"),
    404: _openapi_error_response("Not found"),
    422: _openapi_error_response("Validation error"),
    429: _openapi_error_response("Rate limit exceeded"),
    500: _openapi_error_response("Internal server error"),
    502: _openapi_error_response("Upstream service failed"),
    503: _openapi_error_response("Service unavailable"),
}

COMMON_ERROR_RESPONSES = PUBLIC_ERROR_RESPONSES


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a stable request ID to every request and response."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def get_request_id(request: Request | None) -> str | None:
    if request is None:
        return None

    state = getattr(request, "state", None)
    state_request_id = getattr(state, "request_id", None)
    if state_request_id:
        return str(state_request_id)

    headers = getattr(request, "headers", None)
    header_request_id = headers.get(REQUEST_ID_HEADER) if headers is not None else None
    return header_request_id or None


def build_error_payload(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload = APIErrorResponse(
        errors=[
            APIError(
                status=status_code,
                code=code,
                title=title,
                detail=detail,
                request_id=request_id,
            )
        ]
    )
    return payload.model_dump(exclude_none=True)


def api_error_response(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str | None = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            status_code=status_code,
            code=code,
            title=title,
            detail=detail,
            request_id=request_id,
        ),
        headers=headers,
    )
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


def internal_server_error_response(request: Request) -> JSONResponse:
    return api_error_response(
        status_code=500,
        code="internal_server_error",
        title="Internal server error",
        detail="An unexpected error occurred.",
        request_id=get_request_id(request),
    )


def _safe_detail(status_code: int, detail: Any) -> str | None:
    if status_code >= 500:
        if status_code == 502:
            return "An upstream service failed."
        if status_code == 503:
            return "The service is temporarily unavailable."
        return "An unexpected error occurred."

    if detail is None:
        return None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        for key in ("detail", "message"):
            value = detail.get(key)
            if isinstance(value, str):
                return value
    return "Request validation failed." if status_code == 422 else str(detail)


def _error_code(status_code: int, detail: Any) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("code"), str):
        return detail["code"]
    return _ERROR_CODES.get(status_code, "http_error")


def _error_title(status_code: int, detail: Any) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("title"), str):
        return detail["title"]
    return _ERROR_TITLES.get(status_code, "HTTP error")


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return api_error_response(
        status_code=exc.status_code,
        code=_error_code(exc.status_code, exc.detail),
        title=_error_title(exc.status_code, exc.detail),
        detail=_safe_detail(exc.status_code, exc.detail),
        request_id=get_request_id(request),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return api_error_response(
        status_code=422,
        code="validation_error",
        title="Validation error",
        detail="Request validation failed.",
        request_id=get_request_id(request),
    )
