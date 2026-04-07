import logging
import os
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.tasks.api_usage_enrichment import enrich_api_usage_log
from db.config import DATABASE_URL
from db.models import api_usage_logs

logger = logging.getLogger(__name__)

# Create async engine and session; use NullPool to avoid cross-event-loop issues
engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class APIUsageLogService:
    """Service to log API usage for analytics."""

    async def log_request(
        self,
        request,
        tier_id: int,
        api_key_id: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        status_code: int = 200,
    ):
        """
        Log an API request to the api_usage_logs table.

        This is designed to be called asynchronously and won't block the request.
        Errors are logged but don't affect the request.

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
            # Extract basic request info
            endpoint = request.url.path
            method = request.method

            # Get IP address
            ip_address = self._get_ip_address(request)

            # Get user agent
            user_agent = request.headers.get("User-Agent")

            # Extract referrer
            referrer = request.headers.get("Referer") or request.headers.get("Referrer")
            referring_domain = self._extract_domain(referrer) if referrer else None

            # Extract UTM parameters from query string
            utm_params = self._extract_utm_params(request)

            # Get visit token (if we implement visit tracking later)
            visit_token = request.headers.get("X-Visit-Token")  # Future: generate if not present

            # Extract all query parameters for properties (Ahoy-inspired event properties)
            query_params = dict(request.query_params)
            # Remove UTM params from query_params since they're stored separately
            for utm_key in ["utm_source", "utm_medium", "utm_term", "utm_content", "utm_campaign"]:
                query_params.pop(utm_key, None)

            # Build properties JSON - always include query_params (even if empty dict)
            properties = {
                "query_params": query_params,
            }

            # Build log entry
            log_entry = {
                "api_key_id": api_key_id,
                "tier_id": tier_id,
                "visit_token": visit_token,
                "endpoint": endpoint[:500],  # Truncate to max length
                "method": method[:10],
                "status_code": status_code,
                "requested_at": datetime.utcnow(),
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
                "utm_term": utm_params.get("utm_term")[:255]
                if utm_params.get("utm_term")
                else None,
                "utm_content": utm_params.get("utm_content")[:255]
                if utm_params.get("utm_content")
                else None,
                "utm_campaign": utm_params.get("utm_campaign")[:255]
                if utm_params.get("utm_campaign")
                else None,
                "properties": properties,  # Always store properties (includes query_params)
                # Note: browser, os, device_type, location fields
                # would be populated by background jobs/geocoding services in the future
            }

            # Insert asynchronously
            async with async_session() as session:
                try:
                    logger.info(
                        f"Logging API request: {endpoint} {method} - "
                        f"tier_id={tier_id}, status={status_code}"
                    )
                    stmt = insert(api_usage_logs).values(**log_entry).returning(api_usage_logs.c.id)
                    result = await session.execute(stmt)
                    log_id = result.scalar()
                    await session.commit()
                    logger.info(
                        f"Successfully logged API request: {endpoint} {method} (log_id={log_id})"
                    )

                    # Queue enrichment task (non-blocking, errors logged but
                    # don't affect request)
                    if log_id:
                        try:
                            enrich_api_usage_log.delay(log_id)
                            logger.debug(f"Queued enrichment task for log_id={log_id}")
                        except Exception as enrich_error:
                            # Don't fail the request if enrichment queuing fails
                            logger.warning(
                                f"Failed to queue enrichment task for "
                                f"log_id={log_id}: {enrich_error}"
                            )
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error logging API usage for {endpoint}: {e}", exc_info=True)
                    logger.error("API usage log write failed")

        except Exception as e:
            # Log but don't fail the request
            logger.error(f"Error in API usage logging: {e}", exc_info=True)

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
