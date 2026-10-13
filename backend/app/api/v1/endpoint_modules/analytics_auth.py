"""Analytics password sign-in, separate from API keys and admin access."""

import secrets

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services import analytics_auth as auth

router = APIRouter(prefix="/analytics/auth")
HEADERS = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


class PasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


@router.post("/password", dependencies=[Depends(auth.same_origin)])
def password_login(payload: PasswordRequest, request: Request):
    auth.password_secret()  # Fail closed when the server has no usable secret.
    try:
        # All browsers pass through SSR. Use a shared budget rather than trusting
        # client-supplied forwarding headers to identify individual visitors.
        if auth.limited("password", 30, 900):
            raise HTTPException(429, "Please try again later", headers={"Retry-After": "900"})
        if not auth.password_matches(payload.password):
            raise HTTPException(401, "Incorrect password")
        return create_session(request)
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None


def create_session(request: Request):
    """Rotate the opaque session after successful password authentication."""
    try:
        token = secrets.token_urlsafe(32)
        auth.store().set(
            "analytics:session:" + auth.digest(token), auth.session_revision(), ex=auth.SESSION_TTL
        )
        old = request.cookies.get(auth.COOKIE)
        if old:
            auth.store().delete("analytics:session:" + auth.digest(old))
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None
    response = JSONResponse({"authenticated": True}, headers=HEADERS)
    response.set_cookie(
        auth.COOKIE,
        token,
        max_age=auth.SESSION_TTL,
        httponly=True,
        secure=auth.secure_cookie(),
        samesite="lax",
        path="/",
    )
    return response


@router.get("/session")
def session(identity: str = Depends(auth.require_analytics_session)):
    return JSONResponse({"authenticated": True}, headers=HEADERS)


@router.post("/logout", dependencies=[Depends(auth.same_origin)])
def logout(request: Request):
    token = request.cookies.get(auth.COOKIE)
    try:
        if token:
            auth.store().delete("analytics:session:" + auth.digest(token))
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None
    response = JSONResponse({"authenticated": False}, headers=HEADERS)
    response.delete_cookie(
        auth.COOKIE, path="/", secure=auth.secure_cookie(), httponly=True, samesite="lax"
    )
    return response
