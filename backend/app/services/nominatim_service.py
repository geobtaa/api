import asyncio
import logging
import os
import time
from typing import Any

import requests

from app.services.provider_throttle import (
    provider_request_slot,
    record_provider_failure,
    record_provider_success,
)

logger = logging.getLogger(__name__)

NOMINATIM_SEARCH_URL = os.getenv(
    "NOMINATIM_SEARCH_URL",
    "https://nominatim.openstreetmap.org/search",
)
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "BTAA-Geoportal/1.0 (+https://geo.btaa.org)",
)
NOMINATIM_TIMEOUT_SECONDS = float(os.getenv("NOMINATIM_TIMEOUT_SECONDS", "10"))
NOMINATIM_HARD_MAX_LIMIT = 5
NOMINATIM_MAX_LIMIT = min(
    int(os.getenv("NOMINATIM_MAX_LIMIT", str(NOMINATIM_HARD_MAX_LIMIT))),
    NOMINATIM_HARD_MAX_LIMIT,
)


class NominatimError(Exception):
    """Raised when Nominatim cannot satisfy a request."""


def normalize_nominatim_query(query: str) -> str:
    return " ".join((query or "").strip().split())


def normalize_nominatim_limit(limit: int) -> int:
    return max(1, min(int(limit or NOMINATIM_MAX_LIMIT), NOMINATIM_MAX_LIMIT))


def _failure_type_for_exception(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.Timeout):
        return "timeout"
    if isinstance(exc, requests.ConnectionError):
        return "connection"
    return "request_error"


def _fetch_raw_nominatim_results(
    query: str,
    limit: int,
    accept_language: str | None,
) -> list[dict[str, Any]]:
    params = {
        "q": query,
        "format": "json",
        "limit": str(limit),
        "addressdetails": "1",
        "extratags": "1",
        "namedetails": "1",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": NOMINATIM_USER_AGENT,
    }
    if accept_language:
        headers["Accept-Language"] = accept_language

    started = time.monotonic()
    try:
        with provider_request_slot(NOMINATIM_SEARCH_URL, action="nominatim search"):
            response = requests.get(
                NOMINATIM_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=NOMINATIM_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        record_provider_success(NOMINATIM_SEARCH_URL)
        payload = response.json()
    except requests.RequestException as exc:
        elapsed = time.monotonic() - started
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        record_provider_failure(
            NOMINATIM_SEARCH_URL,
            elapsed_seconds=elapsed,
            failure_type=_failure_type_for_exception(exc),
            status_code=status_code,
        )
        raise NominatimError("Nominatim request failed") from exc
    except ValueError as exc:
        raise NominatimError("Nominatim returned invalid JSON") from exc

    if not isinstance(payload, list):
        logger.warning("Unexpected Nominatim payload type: %s", type(payload).__name__)
        return []

    return [item for item in payload if isinstance(item, dict)]


async def fetch_raw_nominatim_results(
    query: str,
    limit: int,
    accept_language: str | None,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _fetch_raw_nominatim_results,
        query,
        limit,
        accept_language,
    )


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _bounding_box(result: dict[str, Any]) -> tuple[float, float, float, float]:
    lat = _as_float(result.get("lat"))
    lon = _as_float(result.get("lon"))
    bbox = result.get("boundingbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        min_lat = _as_float(bbox[0], lat)
        max_lat = _as_float(bbox[1], lat)
        min_lon = _as_float(bbox[2], lon)
        max_lon = _as_float(bbox[3], lon)
        return min_lat, max_lat, min_lon, max_lon
    return lat, lat, lon, lon


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _place_type(result: dict[str, Any]) -> str:
    addresstype = _clean_string(result.get("addresstype"))
    if addresstype:
        return addresstype

    address = result.get("address")
    if isinstance(address, dict):
        name = _clean_string(result.get("name"))
        for key in (
            "city",
            "town",
            "village",
            "hamlet",
            "municipality",
            "county",
            "state",
            "region",
            "province",
            "country",
        ):
            value = _clean_string(address.get(key))
            if value and (not name or value == name):
                return key

    return _clean_string(result.get("type")) or _clean_string(result.get("class")) or "place"


def transform_nominatim_results(
    results: list[dict[str, Any]],
    *,
    query: str,
    limit: int,
    self_url: str,
) -> dict[str, Any]:
    has_administrative = any(
        result.get("class") in {"boundary", "place"} or result.get("type") == "administrative"
        for result in results
    )

    filtered_results = [
        result
        for result in results
        if not (has_administrative and result.get("class") in {"waterway", "natural", "water"})
    ]

    def sort_key(result: dict[str, Any]) -> tuple[int, float]:
        is_administrative = (
            result.get("class") in {"boundary", "place"} or result.get("type") == "administrative"
        )
        return (0 if is_administrative else 1, -_as_float(result.get("importance")))

    data = []
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for result in sorted(filtered_results, key=sort_key):
        place_id = result.get("place_id")
        min_lat, max_lat, min_lon, max_lon = _bounding_box(result)
        name = str(result.get("name") or result.get("display_name") or "")
        display_name = str(result.get("display_name") or name)
        placetype = _place_type(result)

        data.append(
            {
                "id": f"nominatim-{place_id}",
                "type": "gazetteer_place",
                "attributes": {
                    "id": place_id,
                    "wok_id": place_id,
                    "parent_id": 0,
                    "name": name,
                    "placetype": placetype,
                    "country": "",
                    "repo": "nominatim",
                    "latitude": _as_float(result.get("lat")),
                    "longitude": _as_float(result.get("lon")),
                    "min_latitude": min_lat,
                    "min_longitude": min_lon,
                    "max_latitude": max_lat,
                    "max_longitude": max_lon,
                    "is_current": 1,
                    "is_deprecated": 0,
                    "is_ceased": 0,
                    "is_superseded": 0,
                    "is_superseding": 0,
                    "superseded_by": None,
                    "supersedes": None,
                    "lastmodified": int(time.time() * 1000),
                    "created_at": now,
                    "updated_at": now,
                    "display_name": display_name,
                },
            }
        )

    return {
        "jsonapi": {"version": "1.1", "profile": []},
        "links": {"self": self_url},
        "meta": {
            "totalCount": len(data),
            "totalPages": 1 if data else 0,
            "currentPage": 1,
            "perPage": limit,
            "query": query,
            "offset": 0,
            "gazetteer": "nominatim",
        },
        "data": data,
    }


def empty_nominatim_response(query: str, limit: int, self_url: str = "") -> dict[str, Any]:
    return {
        "jsonapi": {"version": "1.1", "profile": []},
        "links": {"self": self_url},
        "meta": {
            "totalCount": 0,
            "totalPages": 0,
            "currentPage": 1,
            "perPage": limit,
            "query": query,
            "offset": 0,
            "gazetteer": "nominatim",
        },
        "data": [],
    }


async def build_nominatim_search_response(
    *,
    query: str,
    limit: int,
    accept_language: str | None,
    self_url: str,
) -> dict[str, Any]:
    normalized_query = normalize_nominatim_query(query)
    normalized_limit = normalize_nominatim_limit(limit)
    if not normalized_query:
        return empty_nominatim_response(normalized_query, normalized_limit, self_url)

    raw_results = await fetch_raw_nominatim_results(
        normalized_query,
        normalized_limit,
        accept_language,
    )
    return transform_nominatim_results(
        raw_results,
        query=normalized_query,
        limit=normalized_limit,
        self_url=self_url,
    )
