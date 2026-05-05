import logging
import os

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.turnstile_service import TurnstileService, turnstile_enabled

logger = logging.getLogger(__name__)

DEFAULT_PROTECTED_PATHS = (
    "/api/v1/search",
    "/api/v1/suggest",
    "/api/v1/map/h3",
)


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _protected_paths() -> tuple[str, ...]:
    raw_value = os.getenv("TURNSTILE_PROTECTED_PATHS", ",".join(DEFAULT_PROTECTED_PATHS))
    paths = tuple(_split_csv(raw_value))
    return paths or DEFAULT_PROTECTED_PATHS


def _path_matches(path: str, protected_path: str) -> bool:
    return path == protected_path or path.startswith(f"{protected_path}/")


def _has_api_key(request: Request) -> bool:
    if request.headers.get("X-API-Key"):
        return True
    auth_header = request.headers.get("Authorization", "")
    return auth_header.startswith("Bearer ") or bool(request.query_params.get("api_key"))


def _is_frontend_gate_request(request: Request) -> bool:
    if request.headers.get("X-BTAA-Turnstile-Gate"):
        return True
    if request.headers.get("X-BTAA-Client-Channel", "").lower() == "browser":
        return True
    return bool(request.headers.get("X-Visit-Token"))


class TurnstileMiddleware(BaseHTTPMiddleware):
    """Require a verified Turnstile browser session on configured hot paths."""

    def __init__(self, app):
        super().__init__(app)
        self.turnstile_service = TurnstileService()

    async def dispatch(self, request: Request, call_next):
        if not turnstile_enabled() or request.method == "OPTIONS":
            return await call_next(request)

        if not self._should_require_turnstile(request):
            return await call_next(request)

        if await self.turnstile_service.is_session_valid(request):
            return await call_next(request)

        logger.info("Blocking unverified Turnstile request to %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "turnstile_required",
                "message": "A verified browser session is required for this request.",
            },
            headers={"X-Turnstile-Required": "true"},
        )

    def _should_require_turnstile(self, request: Request) -> bool:
        path = request.url.path
        if not any(_path_matches(path, protected_path) for protected_path in _protected_paths()):
            return False

        if _has_api_key(request) and not _is_frontend_gate_request(request):
            return False

        return True
