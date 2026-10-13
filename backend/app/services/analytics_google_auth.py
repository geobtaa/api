"""Google OIDC login with single-use challenges bound to the initiating browser."""

import base64
import hashlib
import json
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.services import analytics_auth as auth

COOKIE = "btaa_analytics_google"
TTL = 600
CALLBACK = "/analytics/google/callback"


def configured() -> bool:
    return bool(
        os.getenv("ANALYTICS_GOOGLE_CLIENT_ID") and os.getenv("ANALYTICS_GOOGLE_CLIENT_SECRET")
    )


def credentials():
    if not configured():
        raise HTTPException(503, "Google sign-in is unavailable")
    return os.environ["ANALYTICS_GOOGLE_CLIENT_ID"], os.environ["ANALYTICS_GOOGLE_CLIENT_SECRET"]


def start(request: Request) -> tuple[str, str]:
    client_id, _ = credentials()
    ip = request.client.host if request.client else "unknown"
    if auth.limited("google:" + auth.digest(ip), 100, 900):
        raise HTTPException(429, "Please try again later")
    state, browser, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    auth.store().set(
        "analytics:google:" + auth.digest(state),
        json.dumps({"browser": auth.digest(browser), "nonce": nonce, "verifier": verifier}),
        ex=TTL,
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": auth.base_url() + CALLBACK,
            "response_type": "code",
            "scope": "openid email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    ), browser


class BoundedGoogleRequest(GoogleRequest):
    def __call__(self, *args, **kwargs):
        kwargs["timeout"] = 10
        return super().__call__(*args, **kwargs)


def finish(code: str, state: str, browser: str) -> str:
    client_id, client_secret = credentials()
    record = auth.store().getdel("analytics:google:" + auth.digest(state))
    if not record or not browser:
        raise HTTPException(400, "Sign-in expired. Please try again")
    challenge = json.loads(record)
    if not secrets.compare_digest(challenge["browser"], auth.digest(browser)):
        raise HTTPException(400, "Sign-in expired. Please try again")
    try:
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "code_verifier": challenge["verifier"],
                "grant_type": "authorization_code",
                "redirect_uri": auth.base_url() + CALLBACK,
            },
            timeout=10,
        )
        response.raise_for_status()
        # Google's library checks signature, issuer, audience and expiration.
        claims = id_token.verify_oauth2_token(
            response.json()["id_token"], BoundedGoogleRequest(), audience=client_id
        )
    except Exception:
        # Provider exceptions can contain codes/tokens; never log them.
        raise HTTPException(400, "Google sign-in could not be verified. Please try again") from None
    if (
        claims.get("nonce") != challenge["nonce"]
        or not claims.get("sub")
        or claims.get("email_verified") is not True
        or not isinstance(claims.get("email"), str)
    ):
        raise HTTPException(403, "This Google account cannot access analytics")
    email = auth.normalize(claims["email"])
    # Google is authoritative for Gmail and managed Workspace addresses. For other
    # addresses, email_verified alone may reflect historical ownership.
    if not (email.endswith("@gmail.com") or claims.get("hd")) or not auth.approved(email):
        raise HTTPException(403, "This Google account cannot access analytics")
    return email
