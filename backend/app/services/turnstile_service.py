import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import redis.asyncio as redis
from fastapi import Request

logger = logging.getLogger(__name__)

TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
DEFAULT_TURNSTILE_ACTION = "geoportal_gate"
DEFAULT_TURNSTILE_COOKIE_NAME = "btaa_turnstile_session"
DEFAULT_TURNSTILE_SESSION_TTL_SECONDS = 3600


def env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def turnstile_enabled() -> bool:
    return env_flag("TURNSTILE_ENABLED", "false")


def turnstile_cookie_name() -> str:
    return os.getenv("TURNSTILE_COOKIE_NAME", DEFAULT_TURNSTILE_COOKIE_NAME).strip()


def turnstile_session_ttl_seconds() -> int:
    raw_value = os.getenv(
        "TURNSTILE_SESSION_TTL_SECONDS",
        str(DEFAULT_TURNSTILE_SESSION_TTL_SECONDS),
    )
    try:
        return max(60, int(raw_value))
    except ValueError:
        logger.warning("Invalid TURNSTILE_SESSION_TTL_SECONDS=%r; using default", raw_value)
        return DEFAULT_TURNSTILE_SESSION_TTL_SECONDS


def _split_csv_env(name: str) -> list[str]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class TurnstileValidationResult:
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error_codes: list[str] = field(default_factory=list)
    status_code: int = 400


class TurnstileService:
    """Validate Cloudflare Turnstile tokens and manage verified browser sessions."""

    _redis_client: redis.Redis | None = None

    def __init__(self):
        self.cookie_name = turnstile_cookie_name()
        self.session_ttl_seconds = turnstile_session_ttl_seconds()

    @property
    def expected_action(self) -> str:
        return os.getenv("TURNSTILE_EXPECTED_ACTION", DEFAULT_TURNSTILE_ACTION).strip()

    @property
    def allowed_hostnames(self) -> list[str]:
        return _split_csv_env("TURNSTILE_ALLOWED_HOSTNAMES")

    @property
    def siteverify_url(self) -> str:
        return os.getenv("TURNSTILE_SITEVERIFY_URL", TURNSTILE_SITEVERIFY_URL).strip()

    def is_enabled(self) -> bool:
        return turnstile_enabled()

    def _redis(self) -> redis.Redis:
        if self.__class__._redis_client is None:
            self.__class__._redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "redis"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                password=os.getenv("REDIS_PASSWORD"),
                db=int(os.getenv("TURNSTILE_REDIS_DB", os.getenv("REDIS_DB", "0"))),
                socket_timeout=float(os.getenv("REDIS_TIMEOUT_SECONDS", "0.5")),
                socket_connect_timeout=float(os.getenv("REDIS_TIMEOUT_SECONDS", "0.5")),
                decode_responses=True,
            )
        return self.__class__._redis_client

    def _session_key(self, session_token: str) -> str:
        return f"turnstile:session:{_sha256_text(session_token)}"

    def extract_session_token(self, request: Request) -> str | None:
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get("X-Turnstile-Session")
        session_token = cookie_token or header_token
        if not session_token:
            return None
        if len(session_token) > 512:
            return None
        return session_token

    async def is_session_valid(self, request: Request) -> bool:
        if not self.is_enabled():
            return True

        session_token = self.extract_session_token(request)
        if not session_token:
            return False

        try:
            return bool(await self._redis().exists(self._session_key(session_token)))
        except Exception as exc:
            logger.warning("Turnstile session lookup failed: %s", exc)
            return False

    async def create_session(self, request: Request) -> str:
        session_token = secrets.token_urlsafe(32)
        user_agent = request.headers.get("User-Agent", "")
        payload = {
            "created_at": int(time.time()),
            "ip": _extract_ip_address(request),
            "user_agent_sha256": _sha256_text(user_agent) if user_agent else None,
        }
        await self._redis().set(
            self._session_key(session_token),
            json.dumps(payload),
            ex=self.session_ttl_seconds,
        )
        return session_token

    async def verify_token(self, token: str, request: Request) -> TurnstileValidationResult:
        if not self.is_enabled():
            return TurnstileValidationResult(success=True, payload={"disabled": True})

        secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
        if not secret:
            logger.error("TURNSTILE_ENABLED=true but TURNSTILE_SECRET_KEY is not set")
            return TurnstileValidationResult(
                success=False,
                error_codes=["missing-server-secret"],
                status_code=503,
            )

        if not token or len(token) > 2048:
            return TurnstileValidationResult(
                success=False,
                error_codes=["missing-input-response" if not token else "invalid-input-response"],
                status_code=400,
            )

        form_data = {
            "secret": secret,
            "response": token,
            "idempotency_key": str(uuid.uuid4()),
        }
        remote_ip = _extract_ip_address(request)
        if remote_ip:
            form_data["remoteip"] = remote_ip

        try:
            timeout = float(os.getenv("TURNSTILE_VERIFY_TIMEOUT_SECONDS", "3"))
            async with httpx.AsyncClient(timeout=timeout) as client:
                payload = await self._siteverify(client, form_data)
        except Exception as exc:
            logger.warning("Turnstile Siteverify request failed: %s", exc)
            return TurnstileValidationResult(
                success=False,
                error_codes=["siteverify-unavailable"],
                status_code=503,
            )

        error_codes = payload.get("error-codes") or []
        if not payload["success"]:
            return TurnstileValidationResult(
                success=False,
                payload=payload,
                error_codes=error_codes,
                status_code=503 if "internal-error" in error_codes else 400,
            )

        expected_action = self.expected_action
        actual_action = str(payload.get("action") or "")
        if expected_action and actual_action != expected_action:
            logger.warning(
                "Turnstile action mismatch: expected %s, got %s",
                expected_action,
                actual_action,
            )
            return TurnstileValidationResult(
                success=False,
                payload=payload,
                error_codes=["invalid-action"],
                status_code=400,
            )

        allowed_hostnames = self.allowed_hostnames
        actual_hostname = str(payload.get("hostname") or "")
        if allowed_hostnames and actual_hostname not in allowed_hostnames:
            logger.warning(
                "Turnstile hostname mismatch: %s not in allowed hostnames",
                actual_hostname,
            )
            return TurnstileValidationResult(
                success=False,
                payload=payload,
                error_codes=["invalid-hostname"],
                status_code=400,
            )

        return TurnstileValidationResult(success=True, payload=payload)

    async def _siteverify(self, client: httpx.AsyncClient, form_data: dict[str, str]) -> dict:
        # A timeout may happen after Cloudflare consumes the single-use token.
        # Reuse the UUID and token for every retry of this validation attempt.
        for attempt in range(3):
            try:
                response = await client.post(self.siteverify_url, data=form_data)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("success"), bool):
                    raise ValueError("Invalid Siteverify response shape")
                errors = payload.get("error-codes") or []
                if not isinstance(errors, list) or any(
                    not isinstance(code, str) for code in errors
                ):
                    raise ValueError("Invalid Siteverify error codes")
                if payload["success"] or "internal-error" not in errors or attempt == 2:
                    return payload
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                retryable = isinstance(exc, httpx.TransportError) or exc.response.status_code >= 500
                if not retryable or attempt == 2:
                    raise
            await asyncio.sleep(0.25 * (2**attempt))
        raise RuntimeError("Siteverify attempts exhausted")


def _extract_ip_address(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return None
