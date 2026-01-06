import logging
import os
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.datastructures import MutableHeaders

logger = logging.getLogger(__name__)


class APIProxyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle /api-proxy/ routes with server-side API key injection.

    This middleware:
    1. Intercepts requests to /api-proxy/*
    2. Rewrites the path to /api/v1/*
    3. Adds the API key header server-side (from environment variable)
    4. Passes the request to normal routing

    This allows the BFF (Backend-for-Frontend) pattern in production without
    requiring nginx or Traefik configuration changes.
    """

    def __init__(self, app):
        super().__init__(app)
        self.api_key = os.getenv("BTAA_GEOSPATIAL_API_KEY")
        if not self.api_key:
            logger.warning(
                "BTAA_GEOSPATIAL_API_KEY not set - /api-proxy/ routes will not work correctly"
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle /api-proxy/ routes."""
        path = request.url.path

        # Check if this is an /api-proxy/ request
        if path.startswith("/api-proxy/"):
            # Rewrite path: /api-proxy/search -> /api/v1/search
            new_path = path.replace("/api-proxy/", "/api/v1/", 1)
            
            # Update the request scope to use the new path
            request.scope["path"] = new_path
            request.scope["raw_path"] = new_path.encode()
            
            # Update query string if needed (preserve original)
            # The URL will be reconstructed from the scope

            # Add API key header server-side (hidden from browser)
            # Modify headers in the scope
            if self.api_key:
                # Get current headers from scope
                headers = list(request.scope.get("headers", []))
                # Add API key header (as bytes, as headers are stored in ASGI)
                headers.append((b"x-api-key", self.api_key.encode()))
                request.scope["headers"] = headers
                
                # Also update the _headers cache if it exists
                if hasattr(request, "_headers"):
                    request._headers = MutableHeaders(headers)

        response = await call_next(request)

        # Rewrite redirect Location headers to go through /api-proxy/
        # This handles cases where the API returns redirects (e.g., static-map → static-maps)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if location:
                # Rewrite /api/v1/ redirects to /api-proxy/
                if location.startswith("/api/v1/"):
                    new_location = location.replace("/api/v1/", "/api-proxy/", 1)
                    response.headers["location"] = new_location
                # Also handle absolute URLs
                elif "/api/v1/" in location:
                    new_location = location.replace("/api/v1/", "/api-proxy/", 1)
                    response.headers["location"] = new_location

        return response
