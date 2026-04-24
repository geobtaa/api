import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.tasks.api_usage_enrichment import write_api_usage_log

logger = logging.getLogger(__name__)


class APIUsageLogService:
    """Service to log API usage for analytics."""

    def _extract_client_properties(self, request) -> Dict[str, str]:
        max_lengths = {
            "client_name": 100,
            "client_version": 100,
            "client_channel": 50,
            "client_instance": 100,
        }
        client_properties = {
            "client_name": request.headers.get("X-BTAA-Client-Name"),
            "client_version": request.headers.get("X-BTAA-Client-Version"),
            "client_channel": request.headers.get("X-BTAA-Client-Channel"),
            "client_instance": request.headers.get("X-BTAA-Client-Instance"),
        }
        return {
            key: value[: max_lengths[key]]
            for key, value in client_properties.items()
            if isinstance(value, str) and value
        }

    def _partition_month(self, timestamp: datetime) -> str:
        month_start = timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.tzinfo is not None:
            month_start = month_start.astimezone(timezone.utc).replace(tzinfo=None)
        return month_start.date().isoformat()

    def _extract_source_host(self, request, referrer: Optional[str]) -> Optional[str]:
        origin = request.headers.get("Origin")
        for candidate in (origin, referrer):
            if not candidate:
                continue
            try:
                parsed = urlparse(candidate)
                if parsed.netloc:
                    return parsed.netloc[:255]
            except Exception:
                continue
        return None

    def _build_log_entry(
        self,
        request,
        tier_id: int,
        api_key_id: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        status_code: int = 200,
    ) -> Dict[str, Any]:
        """Serialize the request into a Celery-safe analytics payload."""
        endpoint = request.url.path
        method = request.method
        ip_address = self._get_ip_address(request)
        user_agent = request.headers.get("User-Agent")
        referrer = request.headers.get("Referer") or request.headers.get("Referrer")
        referring_domain = self._extract_domain(referrer) if referrer else None
        utm_params = self._extract_utm_params(request)
        visit_token = request.headers.get("X-Visit-Token")
        client_properties = self._extract_client_properties(request)
        source_host = self._extract_source_host(request, referrer)
        requested_at = datetime.utcnow()

        query_params = dict(request.query_params)
        for utm_key in ["utm_source", "utm_medium", "utm_term", "utm_content", "utm_campaign"]:
            query_params.pop(utm_key, None)

        properties = {
            "query_params": query_params,
        }
        origin = request.headers.get("Origin")
        if origin:
            properties["origin"] = origin[:500]

        return {
            "api_key_id": api_key_id,
            "tier_id": tier_id,
            "visit_token": visit_token,
            "partition_month": self._partition_month(requested_at),
            "endpoint": endpoint[:500],
            "method": method[:10],
            "status_code": status_code,
            "requested_at": requested_at.isoformat(),
            "response_time_ms": response_time_ms,
            "ip_address": ip_address[:45] if ip_address else None,
            "user_agent": user_agent[:500] if user_agent else None,
            "referrer": referrer[:500] if referrer else None,
            "referring_domain": referring_domain[:255] if referring_domain else None,
            "utm_source": utm_params.get("utm_source")[:255]
            if utm_params.get("utm_source")
            else None,
            "utm_medium": utm_params.get("utm_medium")[:255]
            if utm_params.get("utm_medium")
            else None,
            "utm_term": utm_params.get("utm_term")[:255] if utm_params.get("utm_term") else None,
            "utm_content": utm_params.get("utm_content")[:255]
            if utm_params.get("utm_content")
            else None,
            "utm_campaign": utm_params.get("utm_campaign")[:255]
            if utm_params.get("utm_campaign")
            else None,
            "client_name": client_properties.get("client_name"),
            "client_version": client_properties.get("client_version"),
            "client_channel": client_properties.get("client_channel"),
            "client_instance": client_properties.get("client_instance"),
            "source_host": source_host,
            "properties": properties,
        }

    async def log_request(
        self,
        request,
        tier_id: int,
        api_key_id: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        status_code: int = 200,
    ):
        """
        Queue an API request for asynchronous analytics persistence.

        This path intentionally avoids direct database writes so request
        processing does not wait on analytics storage.

        Args:
            request: FastAPI Request object
            tier_id: ID of the service tier
            api_key_id: ID of the API key (None for anonymous)
            response_time_ms: Response time in milliseconds
            status_code: HTTP status code
        """
        # Fast path: skip logging when disabled or during tests to avoid cross-loop overhead
        if os.getenv("DISABLE_API_USAGE_LOG", "false").lower() == "true":
            return
        if os.getenv("APP_ENV") == "test":
            return

        try:
            log_entry = self._build_log_entry(
                request=request,
                tier_id=tier_id,
                api_key_id=api_key_id,
                response_time_ms=response_time_ms,
                status_code=status_code,
            )
            write_api_usage_log.delay(log_entry)
        except Exception as e:
            logger.warning("Failed to queue API usage log: %s", e, exc_info=True)

    def _get_ip_address(self, request) -> Optional[str]:
        """Extract IP address from request."""
        # Check for forwarded IP (from proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return None

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None

    def _extract_utm_params(self, request) -> Dict[str, Optional[str]]:
        """Extract UTM parameters from query string."""
        utm_params = {}
        for param in ["utm_source", "utm_medium", "utm_term", "utm_content", "utm_campaign"]:
            utm_params[param] = request.query_params.get(param)
        return utm_params
