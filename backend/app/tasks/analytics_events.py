import logging
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.pool import NullPool

from app.tasks.worker import celery_app
from db.config import DATABASE_URL
from db.models import analytics_events, analytics_search_impressions, analytics_searches

logger = logging.getLogger(__name__)


def _sync_database_url() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


sync_engine = create_engine(_sync_database_url(), poolclass=NullPool)


def _truncate(value: Any, max_length: int) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    return value[:max_length]


def _coerce_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            logger.warning("Invalid analytics timestamp: %s", value)
    return datetime.utcnow()


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    return None


def _partition_month_for(timestamp: datetime) -> date:
    return timestamp.date().replace(day=1)


def _normalize_search_row(row: Dict[str, Any]) -> Dict[str, Any]:
    occurred_at = _coerce_timestamp(row.get("occurred_at"))
    return {
        "partition_month": _partition_month_for(occurred_at),
        "search_id": _truncate(row.get("search_id"), 64),
        "visit_token": _truncate(row.get("visit_token"), 255),
        "client_name": _truncate(row.get("client_name"), 100),
        "client_version": _truncate(row.get("client_version"), 100),
        "client_channel": _truncate(row.get("client_channel"), 50),
        "client_instance": _truncate(row.get("client_instance"), 100),
        "source_host": _truncate(row.get("source_host"), 255),
        "query": _truncate(row.get("query"), 5000),
        "search_url": _truncate(row.get("search_url"), 5000),
        "view": _truncate(row.get("view"), 50),
        "page": row.get("page"),
        "per_page": row.get("per_page"),
        "sort": _truncate(row.get("sort"), 100),
        "search_field": _truncate(row.get("search_field"), 100),
        "results_count": row.get("results_count") or 0,
        "total_pages": row.get("total_pages"),
        "zero_results": bool(row.get("zero_results")),
        "occurred_at": occurred_at,
        "properties": _json_value(row.get("properties")),
    }


def _normalize_impression_row(row: Dict[str, Any]) -> Dict[str, Any]:
    occurred_at = _coerce_timestamp(row.get("occurred_at"))
    return {
        "partition_month": _partition_month_for(occurred_at),
        "search_id": _truncate(row.get("search_id"), 64),
        "visit_token": _truncate(row.get("visit_token"), 255),
        "resource_id": _truncate(row.get("resource_id"), 255),
        "rank": row.get("rank"),
        "page": row.get("page"),
        "view": _truncate(row.get("view"), 50),
        "occurred_at": occurred_at,
        "properties": _json_value(row.get("properties")),
    }


def _normalize_event_row(row: Dict[str, Any]) -> Dict[str, Any]:
    occurred_at = _coerce_timestamp(row.get("occurred_at"))
    return {
        "partition_month": _partition_month_for(occurred_at),
        "event_id": _truncate(row.get("event_id"), 64),
        "event_type": _truncate(row.get("event_type"), 100),
        "visit_token": _truncate(row.get("visit_token"), 255),
        "search_id": _truncate(row.get("search_id"), 64),
        "resource_id": _truncate(row.get("resource_id"), 255),
        "client_name": _truncate(row.get("client_name"), 100),
        "client_version": _truncate(row.get("client_version"), 100),
        "client_channel": _truncate(row.get("client_channel"), 50),
        "client_instance": _truncate(row.get("client_instance"), 100),
        "source_host": _truncate(row.get("source_host"), 255),
        "rank": row.get("rank"),
        "page": row.get("page"),
        "view": _truncate(row.get("view"), 50),
        "label": _truncate(row.get("label"), 255),
        "destination_url": _truncate(row.get("destination_url"), 5000),
        "source_component": _truncate(row.get("source_component"), 100),
        "occurred_at": occurred_at,
        "properties": _json_value(row.get("properties")),
    }


def _filter_rows(
    rows: Iterable[Dict[str, Any]],
    normalizer,
    required_keys: Iterable[str],
) -> List[Dict[str, Any]]:
    normalized_rows: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = normalizer(row)
        if not all(normalized.get(key) is not None for key in required_keys):
            continue
        normalized_rows.append(normalized)
    return normalized_rows


@celery_app.task(bind=True, name="write_analytics_batch")
def write_analytics_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist queued analytics batches without blocking API/frontend requests."""
    searches = _filter_rows(
        payload.get("searches") or [],
        _normalize_search_row,
        ("search_id",),
    )
    impressions = _filter_rows(
        payload.get("impressions") or [],
        _normalize_impression_row,
        ("search_id", "resource_id", "rank"),
    )
    events = _filter_rows(
        payload.get("events") or [],
        _normalize_event_row,
        ("event_id", "event_type"),
    )

    try:
        with sync_engine.begin() as conn:
            if searches:
                stmt = pg_insert(analytics_searches).values(searches)
                stmt = stmt.on_conflict_do_nothing(constraint="uq_analytics_searches_identity")
                conn.execute(stmt)

            if impressions:
                stmt = pg_insert(analytics_search_impressions).values(impressions)
                stmt = stmt.on_conflict_do_nothing(
                    constraint="uq_analytics_search_impressions_identity"
                )
                conn.execute(stmt)

            if events:
                stmt = pg_insert(analytics_events).values(events)
                stmt = stmt.on_conflict_do_nothing(constraint="uq_analytics_events_identity")
                conn.execute(stmt)

        return {
            "status": "success",
            "searches": len(searches),
            "impressions": len(impressions),
            "events": len(events),
        }
    except Exception as exc:
        logger.error("Error writing analytics batch: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}
