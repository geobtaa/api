import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.turnstile_service import TurnstileService, turnstile_enabled

logger = logging.getLogger(__name__)
router = APIRouter()


class TurnstileVerifyRequest(BaseModel):
    token: str = Field(..., min_length=1)


@router.get("/turnstile/status", include_in_schema=False)
async def turnstile_status(request: Request):
    service = TurnstileService()
    verified = await service.is_session_valid(request)
    return {
        "data": {
            "type": "turnstile-status",
            "attributes": {
                "enabled": turnstile_enabled(),
                "verified": verified,
            },
        }
    }


@router.post("/turnstile/verify", include_in_schema=False)
async def turnstile_verify(payload: TurnstileVerifyRequest, request: Request):
    service = TurnstileService()
    result = await service.verify_token(payload.token, request)

    if not result.success:
        return JSONResponse(
            status_code=result.status_code,
            content={
                "data": {
                    "type": "turnstile-verification",
                    "attributes": {
                        "verified": False,
                        "error_codes": result.error_codes,
                    },
                }
            },
        )

    if not service.is_enabled():
        return {
            "data": {
                "type": "turnstile-verification",
                "attributes": {
                    "verified": True,
                    "enabled": False,
                },
            }
        }

    try:
        session_token = await service.create_session(request)
    except Exception as exc:
        logger.error("Unable to create Turnstile session: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "data": {
                    "type": "turnstile-verification",
                    "attributes": {
                        "verified": False,
                        "error_codes": ["session-store-unavailable"],
                    },
                }
            },
        )

    response = JSONResponse(
        content={
            "data": {
                "type": "turnstile-verification",
                "attributes": {
                    "verified": True,
                    "expires_in": service.session_ttl_seconds,
                    "session_token": session_token,
                },
            }
        }
    )
    response.set_cookie(
        service.cookie_name,
        session_token,
        max_age=service.session_ttl_seconds,
        httponly=True,
        secure=_secure_cookie(request),
        samesite="lax",
        path="/",
    )
    return response


def _secure_cookie(request: Request) -> bool:
    value = os.getenv("TURNSTILE_COOKIE_SECURE")
    if value is not None:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return os.getenv("APP_ENV") == "production" or request.url.scheme == "https"
