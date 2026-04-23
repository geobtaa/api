from datetime import date, datetime

from app.tasks.analytics_events import (
    _normalize_event_row,
    _normalize_impression_row,
    _normalize_search_row,
)
from app.tasks.api_usage_enrichment import _prepare_log_entry


def test_normalize_search_row_sets_partition_month_from_occurred_at():
    normalized = _normalize_search_row(
        {
            "search_id": "search-123",
            "occurred_at": "2026-04-23T17:42:10",
            "results_count": 12,
        }
    )

    assert normalized["partition_month"] == date(2026, 4, 1)
    assert normalized["occurred_at"] == datetime(2026, 4, 23, 17, 42, 10)


def test_normalize_impression_row_sets_partition_month_from_occurred_at():
    normalized = _normalize_impression_row(
        {
            "search_id": "search-123",
            "resource_id": "stanford-abc123",
            "rank": 1,
            "occurred_at": "2026-04-23T17:42:10",
        }
    )

    assert normalized["partition_month"] == date(2026, 4, 1)
    assert normalized["occurred_at"] == datetime(2026, 4, 23, 17, 42, 10)


def test_normalize_event_row_sets_partition_month_from_occurred_at():
    normalized = _normalize_event_row(
        {
            "event_id": "event-123",
            "event_type": "resource_view",
            "occurred_at": "2026-04-23T17:42:10",
        }
    )

    assert normalized["partition_month"] == date(2026, 4, 1)
    assert normalized["occurred_at"] == datetime(2026, 4, 23, 17, 42, 10)


def test_prepare_log_entry_backfills_partition_month_when_missing():
    prepared = _prepare_log_entry(
        {
            "tier_id": 6,
            "endpoint": "/api/v1/search",
            "method": "GET",
            "status_code": 200,
            "requested_at": "2026-04-23T17:42:10",
        }
    )

    assert prepared["partition_month"] == date(2026, 4, 1)
    assert prepared["requested_at"] == datetime(2026, 4, 23, 17, 42, 10)


def test_prepare_log_entry_preserves_explicit_partition_month():
    prepared = _prepare_log_entry(
        {
            "tier_id": 6,
            "endpoint": "/api/v1/search",
            "method": "GET",
            "status_code": 200,
            "requested_at": "2026-04-23T17:42:10",
            "partition_month": "2026-04-01",
        }
    )

    assert prepared["partition_month"] == date(2026, 4, 1)
