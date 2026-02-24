#!/usr/bin/env python3
"""
Reindex via the *same code path* as the /admin/reindex endpoint.

This intentionally calls:
  app.elasticsearch.index.reindex_resources()

Unlike backend/scripts/reindex.py (the resilient reindexer), this uses the
endpoint's implementation and defaults (i.e., indexes all resources without a
published-only filter).
"""

import asyncio
import logging
import os
import sys
from urllib.parse import parse_qs

from dotenv import load_dotenv
from starlette.requests import Request

# Add backend/ to import path (scripts/ is under backend/scripts/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.endpoint_modules.map import map_h3 as map_h3_endpoint  # noqa: E402
from app.elasticsearch.client import es  # noqa: E402
from app.elasticsearch.index import reindex_resources  # noqa: E402
from app.services.cache_service import ENDPOINT_CACHE, CacheService  # noqa: E402
from db.database import database  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _build_request_for_query(query: str) -> Request:
    """Build a minimal ASGI request used to warm cached endpoint responses."""
    query = query.lstrip("?")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/map/h3",
        "raw_path": b"/api/v1/map/h3",
        "query_string": query.encode("utf-8"),
        "headers": [
            (b"accept", b"application/json"),
            (b"accept-encoding", b"gzip"),
        ],
        "client": ("127.0.0.1", 0),
        "server": ("localhost", 8000),
    }
    return Request(scope)


def _default_warm_queries() -> list[str]:
    """Default map/h3 warmup set: global queries for resolutions 2..8."""
    raw_resolutions = os.getenv("MAP_H3_WARM_RESOLUTIONS", "2,3,4,5,6,7,8")
    resolutions: list[int] = []
    for part in raw_resolutions.split(","):
        value = part.strip()
        if not value:
            continue
        try:
            res = int(value)
        except ValueError:
            logger.warning("Skipping invalid MAP_H3_WARM_RESOLUTIONS value: %s", value)
            continue
        if 2 <= res <= 8:
            resolutions.append(res)
        else:
            logger.warning("Skipping out-of-range H3 resolution for warmup: %s", res)

    if not resolutions:
        resolutions = [2, 3, 4, 5, 6, 7, 8]

    return [f"q=&resolution={res}" for res in sorted(set(resolutions))]


def _extra_warm_queries() -> list[str]:
    """Optional additional query strings, separated by | in env var."""
    raw = os.getenv("MAP_H3_WARM_EXTRA_QUERIES", "").strip()
    if not raw:
        return []
    return [q.strip().lstrip("?") for q in raw.split("|") if q.strip()]


async def _purge_and_warm_map_h3_cache() -> None:
    """Invalidate map-tagged cache entries then warm common /map/h3 queries."""
    if not ENDPOINT_CACHE:
        logger.info("Endpoint cache disabled; skipping map/h3 purge+warm.")
        return

    cache = CacheService()
    deleted = await cache.invalidate_tags(["map"])
    logger.info("Purged map cache entries via tag invalidation: %s", deleted)

    warm_queries = _default_warm_queries() + _extra_warm_queries()
    warmed = 0
    failed = 0

    for query in warm_queries:
        parsed = parse_qs(query, keep_blank_values=True)
        q = parsed.get("q", [""])[0]
        bbox = parsed.get("bbox", [None])[0]
        try:
            resolution = int(parsed.get("resolution", ["5"])[0])
        except (TypeError, ValueError):
            resolution = 5

        request = _build_request_for_query(query)
        try:
            response = await map_h3_endpoint(
                request=request,
                q=q,
                bbox=bbox,
                resolution=resolution,
            )
            if getattr(response, "status_code", 200) == 200:
                warmed += 1
            else:
                failed += 1
                logger.warning(
                    "map/h3 warmup returned non-200 status for query '%s': %s",
                    query,
                    getattr(response, "status_code", "unknown"),
                )
        except Exception as exc:
            failed += 1
            logger.warning("map/h3 warmup failed for query '%s': %s", query, exc)

    logger.info("map/h3 warmup complete: warmed=%s failed=%s", warmed, failed)


async def main() -> None:
    try:
        await database.connect()
        result = await reindex_resources()
        logger.info("Reindex complete: %s", result)
        await _purge_and_warm_map_h3_cache()
    finally:
        try:
            await database.disconnect()
        except Exception:
            pass
        try:
            await es.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
