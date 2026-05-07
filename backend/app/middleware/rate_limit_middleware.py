import logging
import os
import re
import time
from typing import Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.api_key_service import APIKeyService
from app.services.api_usage_log_service import APIUsageLogService
from app.services.rate_limit_service import RateLimitService

logger = logging.getLogger(__name__)


def _rate_limit_enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"


def _bypass_rate_limit_for_tests() -> bool:
    return os.getenv("DISABLE_RATE_LIMIT_FOR_TESTS", "false").lower() == "true"


# Backwards-compatible module-level constants (used by some tests that patch them)
RATE_LIMIT_ENABLED = _rate_limit_enabled()
DISABLE_RATE_LIMIT_FOR_TESTS = _bypass_rate_limit_for_tests()

IMMUTABLE_THUMBNAIL_PATH_RE = re.compile(r"^/api/v1/thumbnails/[0-9a-f]{64}$", re.IGNORECASE)
IMMUTABLE_STATIC_MAP_PATH_RE = re.compile(
    r"^/api/v1/static-map-assets/[0-9a-f]{64}$",
    re.IGNORECASE,
)
HEALTHCHECK_BYPASS_PATHS = {
    "/api/docs",
    "/api/openapi.json",
    "/api/redoc",
}
ANALYTICS_EVENTS_PATH = "/api/v1/analytics/events"
DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE = 120


def _is_immutable_asset_route(path: str) -> bool:
    """Return True for public immutable asset paths that should bypass throttling."""
    return bool(
        IMMUTABLE_THUMBNAIL_PATH_RE.fullmatch(path) or IMMUTABLE_STATIC_MAP_PATH_RE.fullmatch(path)
    )


def _is_healthcheck_route(path: str) -> bool:
    """Return True for lightweight health/documentation routes used by deploy tooling."""
    return path in HEALTHCHECK_BYPASS_PATHS


def _is_analytics_events_route(path: str) -> bool:
    """Return True for the lightweight frontend analytics ingestion endpoint."""
    return path == ANALYTICS_EVENTS_PATH


def _analytics_events_requests_per_minute() -> Optional[int]:
    """Return the analytics-event throttle, independent from API service tiers."""
    raw_value = os.getenv(
        "ANALYTICS_EVENTS_REQUESTS_PER_MINUTE",
        str(DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE),
    ).strip()
    if raw_value.lower() in {"", "none", "unlimited", "false", "off"}:
        return None
    try:
        limit = int(raw_value)
    except ValueError:
        logger.warning(
            "Invalid ANALYTICS_EVENTS_REQUESTS_PER_MINUTE=%r; using default %s",
            raw_value,
            DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE,
        )
        return DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE
    if limit < 0:
        logger.warning(
            "Invalid negative ANALYTICS_EVENTS_REQUESTS_PER_MINUTE=%r; using default %s",
            raw_value,
            DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE,
        )
        return DEFAULT_ANALYTICS_EVENTS_REQUESTS_PER_MINUTE
    return limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting based on API keys and service tiers."""

    def __init__(self, app):
        super().__init__(app)
        self.api_key_service = APIKeyService()
        self.rate_limit_service = RateLimitService()
        self.usage_log_service = APIUsageLogService()

    async def dispatch(self, request: Request, call_next):
        """Process request, optionally enforce rate limiting, and log usage."""

        # Skip rate limiting when test bypass flag is set, unless explicitly forced
        if _bypass_rate_limit_for_tests() and not request.headers.get("X-Force-RateLimit"):
            logger.debug("Rate limiting bypassed for tests (DISABLE_RATE_LIMIT_FOR_TESTS=true)")
            return await call_next(request)

        # CORS preflights do not carry Authorization headers, so charging them
        # against anonymous quota causes authenticated browser clients to 429
        # before their real request can be sent.
        if request.method == "OPTIONS":
            logger.debug("Skipping rate limiting for %s (CORS preflight)", request.url.path)
            return await call_next(request)

        # Extract API key from header or query parameter
        api_key = self._extract_api_key(request)

        # Extract IP address for IP whitelist checks
        request_ip = self._extract_ip_address(request)

        skip_rate_limit_reason = None
        if not _rate_limit_enabled():
            skip_rate_limit_reason = "rate limiting disabled"
        elif _is_healthcheck_route(request.url.path):
            skip_rate_limit_reason = "healthcheck route"
        elif request.url.path.startswith("/api/v1/admin"):
            skip_rate_limit_reason = "admin endpoint"
        elif _is_immutable_asset_route(request.url.path):
            skip_rate_limit_reason = "immutable asset route"

        if skip_rate_limit_reason:
            logger.debug(
                "Skipping rate limiting for %s (%s)", request.url.path, skip_rate_limit_reason
            )
        else:
            logger.debug("Processing rate limiting for %s", request.url.path)

        # Determine tier
        tier_info = await self._get_tier_info(api_key, request_ip)

        if tier_info is None:
            # If we can't determine tier, allow request but log warning
            logger.warning(f"Could not determine tier for request to {request.url.path}")
            return await call_next(request)

        tier_name = tier_info["tier_name"]
        requests_per_minute = tier_info["requests_per_minute"]

        # Get identifier (key hash for authenticated, IP for anonymous)
        identifier = self._get_identifier(request, api_key, tier_info)

        rate_limit_tier_name = tier_name
        rate_limit_identifier = identifier
        rate_limit_requests_per_minute = requests_per_minute
        if skip_rate_limit_reason is None and _is_analytics_events_route(request.url.path):
            analytics_limit = _analytics_events_requests_per_minute()
            rate_limit_tier_name = "analytics_events"
            rate_limit_identifier = self._get_analytics_identifier(request)
            rate_limit_requests_per_minute = analytics_limit

        # Check rate limit (skip check for unlimited tiers)
        remaining = None
        reset_time = None
        if skip_rate_limit_reason is None and rate_limit_requests_per_minute is not None:
            allowed, remaining, reset_time = await self.rate_limit_service.check_rate_limit(
                rate_limit_tier_name,
                rate_limit_identifier,
                rate_limit_requests_per_minute,
            )

            if not allowed:
                # Rate limit exceeded - log and return 429
                try:
                    api_key_id = tier_info.get("api_key_id")
                    tier_id = tier_info.get("tier_id")
                    await self.usage_log_service.log_request(
                        request=request,
                        tier_id=tier_id,
                        api_key_id=api_key_id,
                        response_time_ms=0,  # Request was blocked before processing
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                except Exception as e:
                    logger.error(f"Error logging rate-limited request: {e}")

                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": (
                            f"Rate limit of {rate_limit_requests_per_minute} "
                            "requests per minute exceeded"
                        ),
                        "retry_after": reset_time,
                    },
                )
                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(rate_limit_requests_per_minute)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(reset_time)
                response.headers["Retry-After"] = str(reset_time)
                return response

        # Track request start time for response time calculation
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        # Add rate limit headers only when throttling is active for this request.
        if skip_rate_limit_reason is None:
            if rate_limit_requests_per_minute is not None:
                headers = await self.rate_limit_service.get_rate_limit_headers(
                    rate_limit_tier_name,
                    rate_limit_identifier,
                    rate_limit_requests_per_minute,
                    remaining=remaining,
                    reset_time=reset_time,
                )
            else:
                headers = await self.rate_limit_service.get_rate_limit_headers(
                    rate_limit_tier_name,
                    rate_limit_identifier,
                    rate_limit_requests_per_minute,
                )
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value

        if skip_rate_limit_reason == "healthcheck route":
            return response

        # Log API usage (fire-and-forget, won't block response).
        try:
            api_key_id = tier_info.get("api_key_id")
            tier_id = tier_info.get("tier_id")

            if tier_id is None:
                if tier_info.get("source") == "env:BTAA_GEOSPATIAL_API_KEY":
                    logger.debug(
                        "Skipping API usage logging for configured server API key on %s",
                        request.url.path,
                    )
                else:
                    logger.warning(
                        "No tier_id found while logging API usage for %s", request.url.path
                    )
            else:
                logger.info("Attempting to log API usage for a completed request")
                await self.usage_log_service.log_request(
                    request=request,
                    tier_id=tier_id,
                    api_key_id=api_key_id,
                    response_time_ms=response_time_ms,
                    status_code=response.status_code,
                )
        except Exception as e:
            # Don't fail the request if logging fails
            logger.error(f"Error logging API usage: {e}", exc_info=True)

        return response

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request headers or query parameters."""
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key

        # Check Authorization: Bearer header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Check query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key

        return None

    def _extract_ip_address(self, request: Request) -> Optional[str]:
        """Extract IP address from request.

        Checks X-Forwarded-For header first (for proxies/load balancers),
        then falls back to direct client IP.
        """
        # Check for forwarded IP (from proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return None

    async def _get_tier_info(
        self, api_key: Optional[str], request_ip: Optional[str]
    ) -> Optional[dict]:
        """Get tier information for the request."""
        if api_key:
            # Validate API key and get tier (pass IP for whitelist check)
            tier_info = await self.api_key_service.validate_api_key(api_key, request_ip)
            if tier_info:
                return tier_info
            # Invalid key or IP restriction, treat as anonymous
            logger.warning(
                "Invalid API key provided or IP restriction failed, treating as anonymous"
            )

        # No key or invalid key - use anonymous tier
        return await self.api_key_service.get_anonymous_tier()

    def _get_identifier(self, request: Request, api_key: Optional[str], tier_info: dict) -> str:
        """Get identifier for rate limiting (key hash or IP address)."""
        if api_key and "key_hash" in tier_info:
            # Use key hash for authenticated requests
            return tier_info["key_hash"]

        # Use IP address for anonymous requests
        ip_address = self._extract_ip_address(request)
        if ip_address:
            return ip_address

        # Last resort: use a default identifier
        return "unknown"

    def _get_analytics_identifier(self, request: Request) -> str:
        """Use a per-client identifier for analytics event throttling."""
        ip_address = self._extract_ip_address(request)
        if ip_address:
            return f"ip:{ip_address}"
        origin = request.headers.get("Origin")
        if origin:
            return f"origin:{origin}"
        return "unknown"
