from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from urllib3.exceptions import ProtocolError

logger = logging.getLogger(__name__)

# Retry on transient connection errors (server closed connection, timeouts, etc.)
BRIDGE_FETCH_MAX_RETRIES = int(os.getenv("KITHE_BRIDGE_FETCH_MAX_RETRIES", "5"))
BRIDGE_FETCH_RETRY_BACKOFF_SECONDS = float(
    os.getenv("KITHE_BRIDGE_FETCH_RETRY_BACKOFF_SECONDS", "5.0")
)


@dataclass
class BridgePage:
    data: List[Dict[str, Any]]
    next_cursor: Optional[str]
    has_more: bool


class KitheBridgeClient:
    """Small client for the production Geoportal bridge endpoint."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        page_size: Optional[int] = None,
        request_timeout: Optional[int] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("KITHE_BRIDGE_URL", "")).strip()
        self.token = (token or os.getenv("KITHE_BRIDGE_TOKEN", "")).strip()
        self.page_size = int(page_size or os.getenv("KITHE_BRIDGE_PAGE_SIZE", "500"))
        self.request_timeout = int(
            request_timeout or os.getenv("KITHE_BRIDGE_REQUEST_TIMEOUT", "30")
        )
        self.session = session or requests.Session()

        if not self.base_url:
            raise ValueError("KITHE_BRIDGE_URL is required")
        if not self.token:
            raise ValueError("KITHE_BRIDGE_TOKEN is required")

    def fetch_page(
        self, *, cursor: Optional[str] = None, limit: Optional[int] = None
    ) -> BridgePage:
        params: Dict[str, Any] = {"limit": int(limit or self.page_size)}
        if cursor:
            params["cursor"] = cursor

        for attempt in range(BRIDGE_FETCH_MAX_RETRIES):
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    headers={"X-Bridge-Token": self.token},
                    timeout=self.request_timeout,
                )
                response.raise_for_status()
                break
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                ProtocolError,
                OSError,
            ) as exc:
                if attempt + 1 >= BRIDGE_FETCH_MAX_RETRIES:
                    raise
                delay = BRIDGE_FETCH_RETRY_BACKOFF_SECONDS * (2**attempt)
                logger.warning(
                    "Bridge fetch failed (attempt %s/%s), retrying in %.1fs: %s",
                    attempt + 1,
                    BRIDGE_FETCH_MAX_RETRIES,
                    delay,
                    exc,
                )
                time.sleep(delay)

        payload = response.json()
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise ValueError("Bridge response `data` must be a list")

        next_cursor = payload.get("next_cursor")
        has_more = bool(payload.get("has_more"))
        if has_more and not next_cursor:
            raise ValueError("Bridge response indicated more pages but did not return next_cursor")

        return BridgePage(data=data, next_cursor=next_cursor, has_more=has_more)
