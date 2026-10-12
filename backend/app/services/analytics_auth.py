"""Passwordless access to analytics. Redis stores hashes, never bearer tokens."""

import hashlib
import json
import logging
import os
import re
import secrets
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from urllib.parse import urlsplit

import redis
from fastapi import HTTPException, Request

from app.services.feedback_service import deliver_email

logger = logging.getLogger(__name__)
COOKIE = "btaa_analytics_session"
LINK_TTL = 24 * 60 * 60
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


def normalize(email: str) -> str:
    return email.strip().lower()


def approved(email: str) -> bool:
    filename = os.getenv("ANALYTICS_APPROVED_EMAILS_FILE")
    try:
        addresses = (
            json.loads(Path(filename).read_text())
            if filename
            else re.split(r"[,;\n]", os.getenv("ANALYTICS_APPROVED_EMAILS", ""))
        )
        return isinstance(addresses, list) and email in {
            normalize(value) for value in addresses if isinstance(value, str)
        }
    except (OSError, ValueError):
        return False


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


def send_link(email: str):
    """Runs after the generic response; failures never expose approval status."""
    token = secrets.token_urlsafe(32)
    key = "analytics:link:" + digest(token)
    try:
        if not approved(email):
            return
        store().set(key, email, ex=LINK_TTL)
        message = EmailMessage()
        message["From"] = "BTAA Geoportal <no-reply@geo.btaa.org>"
        message["To"] = email
        message["Subject"] = "Your BTAA analytics sign-in link"
        message["Date"] = formatdate(localtime=False, usegmt=True)
        message["Message-ID"] = make_msgid(domain="geo.btaa.org")
        message.set_content(
            "Use this link to sign in to BTAA analytics. It expires in 24 hours "
            "and can be used once. After signing in, you will have access for 24 hours.\n\n"
            f"{base_url()}/analytics/login#token={token}\n\n"
            "If you did not request this link, you can ignore this email."
        )
        return deliver_email(message)
    except Exception:
        # Do not log recipients, tokens, message contents, or SMTP exception details.
        logger.error("Analytics sign-in email delivery failed")
        try:
            store().delete(key)
        except redis.RedisError:
            pass


def require_analytics_session(request: Request) -> str:
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(401, "Sign in to analytics")
    try:
        email = store().get("analytics:session:" + digest(token))
    except redis.RedisError:
        raise HTTPException(503, "Analytics login is unavailable") from None
    if not email or not approved(email):
        raise HTTPException(401, "Sign in to analytics")
    return email
