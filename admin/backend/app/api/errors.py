"""One safe error shape across validation, authentication, domain and routing failures."""

from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.contracts import ErrorDetail, ErrorResponse, ValidationIssue


def error_response(status: int, code: str, message: str, *, errors=None, headers=None):
    body = ErrorResponse(detail=ErrorDetail(code=code, message=message, errors=errors or []))
    return JSONResponse(body.model_dump(mode="json"), status_code=status, headers=headers)


async def http_error(_: Request, exc: HTTPException):
    codes = {
        401: "unauthenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        410: "expired",
        422: "validation_error",
        503: "unavailable",
    }
    # HTTPException details are server-authored; do not include request input in errors.
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return error_response(
        exc.status_code, codes.get(exc.status_code, "http_error"), message, headers=exc.headers
    )


async def validation_error(_: Request, exc: RequestValidationError):
    issues = [
        ValidationIssue(loc=list(item["loc"]), msg=item["msg"], type=item["type"])
        for item in exc.errors()
    ]
    return error_response(422, "validation_error", "Check the supplied fields.", errors=issues)
