from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
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


COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    500: {
        "model": APIErrorResponse,
        "description": "Internal server error",
    },
}


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

    state_request_id = getattr(request.state, "request_id", None)
    if state_request_id:
        return str(state_request_id)

    header_request_id = request.headers.get(REQUEST_ID_HEADER)
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
