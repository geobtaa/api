"""Shared-password analytics access with opaque, revocable Redis sessions."""

import hashlib
import hmac
import os
import re
import secrets
from urllib.parse import urlsplit

import redis
from fastapi import HTTPException, Request

COOKIE = "btaa_analytics_session"
SESSION_TTL = 24 * 60 * 60


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def store():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD"),
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
        socket_timeout=3,
        socket_connect_timeout=3,
    )


def base_url() -> str:
    value = os.getenv("ANALYTICS_BASE_URL", os.getenv("APPLICATION_URL", "http://localhost:3000"))
    if os.getenv("APP_ENV") == "production" and not (
        os.getenv("ANALYTICS_BASE_URL") or os.getenv("APPLICATION_URL")
    ):
        raise HTTPException(503, "Analytics login is unavailable")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(503, "Analytics login is unavailable")
    if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise HTTPException(503, "Analytics login requires HTTPS")
    return f"{parsed.scheme}://{parsed.netloc}"


def same_origin(request: Request):
    if request.headers.get("origin") != base_url():
        raise HTTPException(403, "Invalid request origin")


def secure_cookie() -> bool:
    # HTTP is supported only for explicit local development.
    return urlsplit(base_url()).hostname not in ("localhost", "127.0.0.1", "::1")


def limited(key: str, maximum: int, ttl: int) -> bool:
    # Atomic increment + expiry, including simultaneous first requests.
    count = store().eval(
        "local n=redis.call('INCR',KEYS[1]); "
        "if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
        1,
        "analytics:rate:" + key,
        ttl,
    )
    return count > maximum


def password_secret() -> str:
    value = os.getenv("ANALYTICS_PASSWORD", "")
    if len(value) < 20:
        raise HTTPException(503, "Analytics sign-in is unavailable")
    return value


def password_matches(candidate: str) -> bool:
    # Compare the configured secret directly; no password digest is stored.
    # UTF-8 bytes also allow non-ASCII secrets with constant-time comparison.
    return secrets.compare_digest(candidate.encode(), password_secret().encode())


def session_revision() -> str:
    # A change to the shared password invalidates every existing session.
    return hmac.new(
        password_secret().encode(), b"analytics-shared-password-session-v1", hashlib.sha256
    ).hexdigest()


def require_analytics_session(request: Request) -> str:
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(401, "Sign in to analytics")
    try:
        revision = store().get("analytics:session:" + digest(token))
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None
    if not revision or not secrets.compare_digest(revision, session_revision()):
        raise HTTPException(401, "Sign in to analytics")
    return "shared-password"
