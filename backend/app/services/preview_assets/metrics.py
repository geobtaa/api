"""Structured, content-free delivery metrics for preview asset responses."""

import json
import logging
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from starlette.responses import Response

logger = logging.getLogger(__name__)


def summarize(records, stale_days=30, now=None):
    """Summarize latest attempts and retained manifests; never a success-rate estimate."""
    now = now or datetime.now(timezone.utc)
    statuses, thumbnails, providers, formats = Counter(), Counter(), Counter(), Counter()
    source_formats = Counter()
    seconds, read_bytes, output_bytes, count = 0.0, 0, 0, 0
    stale = []
    for row in records:
        count += 1
        attempt = row.get("last_attempt") or row.get("manifest") or {}
        active = row.get("active_manifest") or row.get("manifest") or {}
        status = attempt.get("status", "unknown")
        statuses[status] += 1
        thumbnails[attempt.get("thumbnail_status", "unsupported")] += 1
        metrics = attempt.get("metrics", {})
        seconds += metrics.get("seconds", 0)
        read_bytes += metrics.get("bytes_read", 0)
        output_bytes += metrics.get("output_bytes", 0)
        sources = metrics.get("source_attempts", [])
        if not sources:
            sources = [{"url": attempt.get("source_url"), "status": status}]
        for source in sources:
            host = urlsplit(source.get("url") or "").hostname or "unknown"
            providers[f"{host} | {source.get('status', status)}"] += 1
            if source.get("kind"):
                source_formats[f"{source['kind']} | {source.get('status', status)}"] += 1
        for layer in attempt.get("layers", []):
            formats[f"{layer.get('format', 'unknown')} | {status}"] += 1
        generated = active.get("generated_at")
        if generated:
            instant = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=timezone.utc)
            if now - instant > timedelta(days=stale_days):
                stale.append(row.get("resource_id") or row.get("id"))
    return {
        "records": count,
        "latest_attempt_outcomes": dict(statuses),
        "thumbnail_outcomes": dict(thumbnails),
        "provider_attempts": dict(providers),
        "layer_formats": dict(formats),
        "processing_seconds": round(seconds, 3),
        "source_format_attempts": dict(source_formats),
        "bytes_read": read_bytes,
        "output_bytes": output_bytes,
        "stale_after_days": stale_days,
        "stale_resource_ids": stale,
        "note": "Latest stored attempts only; not historical totals or a collection success rate.",
    }


class MeteredAssetResponse(Response):
    def __init__(self, response, resource_id, suffix):
        super().__init__(status_code=response.status_code, headers=dict(response.headers))
        self.response = response
        self.resource_id = resource_id
        self.suffix = suffix

    async def __call__(self, scope, receive, send):
        started, emitted, status, complete = time.monotonic(), 0, self.status_code, False

        async def measured(message):
            nonlocal emitted, status, complete
            await send(message)
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                emitted += len(message.get("body", b""))
                complete = not message.get("more_body", False)

        # FileResponse must emit ordinary body chunks so byte counts also cover
        # local files. Object-storage streaming already uses the same messages.
        scope = {
            **scope,
            "extensions": {
                key: value
                for key, value in scope.get("extensions", {}).items()
                if key != "http.response.pathsend"
            },
        }
        try:
            await self.response(scope, receive, measured)
        finally:
            delivery = {
                "resource_id": self.resource_id,
                "format": self.suffix,
                "method": scope["method"],
                "status": status,
                "bytes": emitted,
                "complete": complete,
                "seconds": round(time.monotonic() - started, 4),
            }
            logger.info(
                "preview_asset_delivery %s",
                json.dumps(delivery),
                extra={"preview_delivery": delivery},
            )
