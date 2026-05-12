from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Any

from app.services.search_service import SearchService

SIGNATURE_VERSION = "v0"
DEFAULT_RESULT_LIMIT = 5
MAX_SLACK_TEXT_LENGTH = 2900


@dataclass(frozen=True)
class SlackCommand:
    action: str
    query: str | None = None


def verify_slack_signature(
    *,
    signing_secret: str | None,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    now: int | None = None,
    max_age_seconds: int = 60 * 5,
) -> bool:
    """Verify Slack's request signature for slash command payloads."""
    if not signing_secret or not timestamp or not signature:
        return False

    try:
        request_time = int(timestamp)
    except ValueError:
        return False

    current_time = int(time.time()) if now is None else now
    if abs(current_time - request_time) > max_age_seconds:
        return False

    base_string = b":".join([SIGNATURE_VERSION.encode(), timestamp.encode(), body])
    digest = hmac.new(signing_secret.encode(), base_string, hashlib.sha256).hexdigest()
    expected = f"{SIGNATURE_VERSION}={digest}"
    return hmac.compare_digest(expected, signature)


def parse_slack_command(text: str | None) -> SlackCommand:
    """Parse a compact slash command grammar.

    Supported examples:
    - /btaa
    - /btaa help
    - /btaa search lakes
    - /btaa lakes
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return SlackCommand(action="help")

    verb, _, rest = cleaned.partition(" ")
    normalized_verb = verb.lower()
    query = rest.strip() or None

    if normalized_verb in {"help", "?"}:
        return SlackCommand(action="help")
    if normalized_verb in {"search", "find"}:
        return SlackCommand(action="search", query=query)

    return SlackCommand(action="search", query=cleaned)


async def handle_slack_command(form_data: dict[str, Any]) -> dict[str, Any]:
    command = parse_slack_command(_first_form_value(form_data.get("text")))
    if command.action == "help":
        return help_response()
    if command.action == "search":
        return await search_response(command.query)

    return help_response()


def help_response() -> dict[str, Any]:
    command = os.getenv("SLACK_BOT_COMMAND", "/btaa")
    text = (
        f"Try `{command} search minnesota lakes`, `{command} sanborn maps`, "
        f"or `{command} help`."
    )
    return {
        "response_type": "ephemeral",
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*BTAA Geoportal*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        ],
    }


async def search_response(query: str | None) -> dict[str, Any]:
    if not query:
        return help_response()

    search_service = SearchService()
    results = await search_service.search(
        q=query,
        page=1,
        limit=DEFAULT_RESULT_LIMIT,
        hydrate_hits=True,
        sanitize_response=True,
    )
    if isinstance(results, dict) and results.get("error"):
        return _error_response("Search failed. Please try again in a moment.")

    items = _extract_items(results)
    total = _extract_total(results, fallback=len(items))
    if not items:
        return {
            "response_type": "ephemeral",
            "text": f"No BTAA Geoportal results found for `{query}`.",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"No BTAA Geoportal results found for `{query}`.",
                    },
                }
            ],
        }

    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*BTAA Geoportal results for `{query}`* ({total:,} found)",
            },
        }
    ]
    for item in items[:DEFAULT_RESULT_LIMIT]:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": _format_item(item)}})
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Open full search"},
                    "url": _search_url(query),
                }
            ],
        }
    )

    return {
        "response_type": "ephemeral",
        "text": f"BTAA Geoportal results for {query}",
        "blocks": blocks,
    }


def _error_response(message: str) -> dict[str, Any]:
    return {
        "response_type": "ephemeral",
        "text": message,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": message}}],
    }


def _extract_items(results: Any) -> list[dict[str, Any]]:
    if not isinstance(results, dict):
        return []
    data = results.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        nested = data.get("data")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def _extract_total(results: Any, *, fallback: int) -> int:
    if not isinstance(results, dict):
        return fallback
    meta = results.get("meta")
    if isinstance(meta, dict):
        for key in ("totalCount", "total_count", "total"):
            value = meta.get(key)
            if isinstance(value, int):
                return value
    data = results.get("data")
    if isinstance(data, dict):
        nested_meta = data.get("meta")
        if isinstance(nested_meta, dict):
            value = nested_meta.get("totalCount")
            if isinstance(value, int):
                return value
    return fallback


def _format_item(item: dict[str, Any]) -> str:
    attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    title = _first_present(
        attributes,
        "title",
        "dct_title_s",
        ("ogm", "dct_title_s"),
        ("b1g", "title"),
    )
    resource_id = str(item.get("id") or attributes.get("id") or "").strip()
    provider = _first_present(
        attributes,
        "provider",
        "schema_provider_s",
        ("ogm", "schema_provider_s"),
        ("b1g", "provider"),
    )
    year = _first_present(attributes, "year", "gbl_indexyear_im", ("ogm", "gbl_indexyear_im"))

    title = title or resource_id or "Untitled resource"
    if resource_id:
        line = f"*<{_resource_url(resource_id)}|{_truncate(title, 120)}>*"
    else:
        line = f"*{title}*"
    details = " | ".join(part for part in (_stringify(provider), _stringify(year)) if part)
    if details:
        line = f"{line}\n{details}"
    return _truncate(line, MAX_SLACK_TEXT_LENGTH)


def _first_present(data: dict[str, Any], *keys: str | tuple[str, str]) -> str | int | None:
    for key in keys:
        if isinstance(key, tuple):
            current = data.get(key[0])
            value = current.get(key[1]) if isinstance(current, dict) else None
        else:
            value = data.get(key)
        if value not in (None, "", []):
            if isinstance(value, list):
                return value[0] if value else None
            return value
    return None


def _first_form_value(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value is not None else None


def _stringify(value: Any) -> str | None:
    if value in (None, "", []):
        return None
    if isinstance(value, list):
        return ", ".join(str(item) for item in value[:2] if item not in (None, ""))
    return str(value)


def _base_url() -> str:
    base = (
        os.getenv("GEOPORTAL_BASE_URL")
        or os.getenv("APPLICATION_URL")
        or os.getenv("BTAA_GEOSPATIAL_API_BASE_URL")
        or "https://geoportal.btaa.org"
    )
    base = base.rstrip("/")
    if base.endswith("/api/v1"):
        base = base[: -len("/api/v1")]
    return base


def _resource_url(resource_id: str) -> str:
    return f"{_base_url()}/resources/{resource_id}"


def _search_url(query: str) -> str:
    from urllib.parse import urlencode

    return f"{_base_url()}/search?{urlencode({'q': query})}"


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return f"{value[: length - 3]}..."
