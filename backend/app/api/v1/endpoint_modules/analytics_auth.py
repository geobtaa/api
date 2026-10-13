"""Analytics sign-in endpoints, separate from event ingestion and admin access."""

import re
import secrets

import redis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services import analytics_auth as auth
from app.services import analytics_google_auth as google
from app.services.feedback_service import email_preview_enabled

router = APIRouter(prefix="/analytics/auth")
HEADERS = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class VerifyRequest(BaseModel):
    token: str = Field(min_length=43, max_length=43)


@router.post("/request", dependencies=[Depends(auth.same_origin)])
def request_link(payload: LoginRequest, request: Request, tasks: BackgroundTasks):
    email = auth.normalize(payload.email)
    local, separator, domain = email.partition("@")
    # Linear checks avoid overlapping regex repetitions on untrusted addresses.
    if (
        not local
        or not separator
        or "@" in domain
        or "." not in domain[1:-1]
        or any(char.isspace() or ord(char) < 32 or char in "<>" for char in email)
    ):
        raise HTTPException(422, "Enter a valid email address")
    try:
        ip = request.client.host if request.client else "unknown"
        if auth.limited("ip:" + auth.digest(ip), 100, 900):
            raise HTTPException(429, "Please try again later", headers={"Retry-After": "900"})
        throttled = auth.limited("email:" + auth.digest(email), 3, 900)
        if email_preview_enabled():
            if throttled:
                raise HTTPException(429, "Please try again later", headers={"Retry-After": "900"})
            if not auth.approved(email):
                return JSONResponse(
                    {"preview_error": "This address is not on the local approved list."},
                    status_code=202,
                    headers=HEADERS,
                )
            result = auth.send_link(email)
            if result and result.get("preview"):
                return JSONResponse(result, status_code=202, headers=HEADERS)
            raise HTTPException(503, "Local email preview is unavailable")
        if not throttled:
            tasks.add_task(auth.send_link, email)
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None
    return JSONResponse(
        {"message": "If this address is approved, a sign-in link will arrive shortly."},
        status_code=202,
        headers=HEADERS,
    )


@router.post("/verify", dependencies=[Depends(auth.same_origin)])
def verify(payload: VerifyRequest, request: Request):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", payload.token):
        raise HTTPException(400, "This link is invalid or expired")
    try:
        email = auth.store().getdel("analytics:link:" + auth.digest(payload.token))
        if not email or not auth.approved(email):
            raise HTTPException(400, "This link is invalid or expired")
        return create_session(email, request)
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None


def create_session(email: str, request: Request):
    """Rotate the opaque session after either email or Google authentication."""
    try:
        token = secrets.token_urlsafe(32)
        auth.store().set("analytics:session:" + auth.digest(token), email, ex=auth.SESSION_TTL)
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
def session(email: str = Depends(auth.require_analytics_session)):
    return JSONResponse({"email": email}, headers=HEADERS)


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


@router.get("/options")
def login_options():
    return JSONResponse({"google": google.configured()}, headers=HEADERS)


@router.post("/google/start", dependencies=[Depends(auth.same_origin)])
def google_start(request: Request):
    try:
        url, browser = google.start(request)
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None
    response = JSONResponse({"url": url}, headers=HEADERS)
    response.set_cookie(
        google.COOKIE,
        browser,
        max_age=google.TTL,
        httponly=True,
        secure=auth.secure_cookie(),
        samesite="lax",
        path="/",
    )
    return response


class GoogleCallback(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


@router.post("/google/callback", dependencies=[Depends(auth.same_origin)])
def google_callback(payload: GoogleCallback, request: Request):
    try:
        email = google.finish(payload.code, payload.state, request.cookies.get(google.COOKIE, ""))
        response = create_session(email, request)
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None
    response.delete_cookie(
        google.COOKIE, path="/", secure=auth.secure_cookie(), httponly=True, samesite="lax"
    )
    return response
