import json
import logging
import os
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.tasks.analytics_events import write_analytics_batch

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_source_host(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        try:
            parsed = urlparse(value)
            if parsed.netloc:
                return parsed.netloc[:255]
        except Exception:
            continue
    return None


def _request_defaults(request: Request) -> Dict[str, Any]:
    headers = request.headers
    return {
        "visit_token": headers.get("X-Visit-Token"),
        "client_name": headers.get("X-BTAA-Client-Name"),
        "client_version": headers.get("X-BTAA-Client-Version"),
        "client_channel": headers.get("X-BTAA-Client-Channel"),
        "client_instance": headers.get("X-BTAA-Client-Instance"),
        "source_host": _extract_source_host(
            headers.get("Origin"),
            headers.get("Referer"),
            headers.get("Referrer"),
        ),
    }


def _merge_defaults(row: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(row)
    for key, value in defaults.items():
        if merged.get(key) is None and value is not None:
            merged[key] = value
    return merged


@router.post("/analytics/events")
async def ingest_analytics_events(request: Request):
    """Accept lightweight analytics batches and queue persistence off the request path."""
    if os.getenv("DISABLE_ANALYTICS_EVENTS", "false").lower() == "true":
        return JSONResponse(content={"status": "disabled"}, status_code=202)

    raw_body = await request.body()
    if not raw_body:
        return JSONResponse(content={"status": "ignored", "reason": "empty"}, status_code=202)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse(
            content={"error": "Invalid analytics payload"},
            status_code=400,
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            content={"error": "Invalid analytics payload"},
            status_code=400,
        )

    defaults = _request_defaults(request)
    queued_payload = {
        "searches": [
            _merge_defaults(row, defaults)
            for row in payload.get("searches", [])
            if isinstance(row, dict)
        ],
        "impressions": [
            _merge_defaults(row, defaults)
            for row in payload.get("impressions", [])
            if isinstance(row, dict)
        ],
        "events": [
            _merge_defaults(row, defaults)
            for row in payload.get("events", [])
            if isinstance(row, dict)
        ],
    }

    if not any(queued_payload.values()):
        return JSONResponse(content={"status": "ignored", "reason": "empty"}, status_code=202)

    try:
        write_analytics_batch.delay(queued_payload)
    except Exception as exc:
        logger.warning("Failed to enqueue analytics batch: %s", exc, exc_info=True)

    return JSONResponse(content={"status": "accepted"}, status_code=202)
