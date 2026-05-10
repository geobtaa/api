from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import CliConfig


@dataclass
class CommandAnalytics:
    config: CliConfig
    no_analytics: bool = False
    command: str = ""
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def enabled(self) -> bool:
        return self.config.analytics_enabled and not self.no_analytics

    def event_payload(
        self,
        event_type: str,
        *,
        properties: dict[str, Any] | None = None,
        resource_id: str | None = None,
        search_id: str | None = None,
    ) -> dict[str, Any]:
        safe_properties = dict(properties or {})
        safe_properties.pop("api_key", None)
        safe_properties.pop("output_path", None)
        return {
            "events": [
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": event_type,
                    "resource_id": resource_id,
                    "search_id": search_id,
                    "client_name": "btaa-geo-api-cli",
                    "client_channel": "cli",
                    "client_instance": self.config.client_instance,
                    "source_component": f"btaa-geo-api {self.command}".strip(),
                    "label": self.command,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "properties": safe_properties,
                }
            ]
        }

    def record_event(
        self,
        client,
        event_type: str,
        *,
        properties: dict[str, Any] | None = None,
        resource_id: str | None = None,
        search_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        try:
            client.post(
                "/analytics/events",
                json=self.event_payload(
                    event_type,
                    properties=properties,
                    resource_id=resource_id,
                    search_id=search_id,
                ),
            )
        except Exception:
            return

    def record_search(
        self, client, payload: dict[str, Any], query: str | None, params: dict[str, Any]
    ) -> None:
        if not self.enabled:
            return
        search_id = str(uuid.uuid4())
        data = payload.get("data", []) if isinstance(payload, dict) else []
        meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
        rows = data if isinstance(data, list) else []
        impressions = [
            {
                "search_id": search_id,
                "resource_id": row.get("id"),
                "rank": index + 1,
                "page": params.get("page", 1),
                "view": "cli",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "properties": {},
            }
            for index, row in enumerate(rows)
            if isinstance(row, dict) and row.get("id")
        ]
        event = self.event_payload(
            "cli.command.search",
            properties={
                "command": "search",
                "duration_ms": int((time.perf_counter() - self.started_at) * 1000),
                "result_count": len(rows),
                "total_count": meta.get("totalCount") or meta.get("total_count"),
                "include_filter_fields": sorted(
                    key for key in params if str(key).startswith("include_filters[")
                ),
                "exclude_filter_fields": sorted(
                    key for key in params if str(key).startswith("exclude_filters[")
                ),
            },
            search_id=search_id,
        )["events"][0]
        batch = {
            "searches": [
                {
                    "search_id": search_id,
                    "query": query or "",
                    "view": "cli",
                    "page": params.get("page", 1),
                    "per_page": params.get("per_page"),
                    "sort": params.get("sort"),
                    "search_field": params.get("search_field"),
                    "results_count": len(rows),
                    "total_pages": meta.get("totalPages") or meta.get("total_pages"),
                    "zero_results": len(rows) == 0,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "properties": {"params": _safe_params(params)},
                }
            ],
            "impressions": impressions,
            "events": [event],
        }
        try:
            client.post("/analytics/events", json=batch)
        except Exception:
            return


def _safe_params(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if "api_key" not in str(k).lower()}


@contextmanager
def command_timer() -> Iterator[float]:
    start = time.perf_counter()
    yield start
