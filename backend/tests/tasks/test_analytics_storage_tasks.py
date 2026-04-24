from datetime import date, datetime

from app.tasks.analytics_events import (
    _normalize_event_row,
    _normalize_impression_row,
    _normalize_search_row,
)
from app.tasks.api_usage_enrichment import _prepare_log_entry
from db.migrations.rename_api_usage_logs_to_analytics_api_usage_logs import (
    _build_copy_column_sql,
)


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


def test_legacy_api_usage_log_copy_derives_partition_month_and_source_fields():
    insert_sql, select_sql = _build_copy_column_sql(
        [
            "id",
            "partition_month",
            "requested_at",
            "referring_domain",
            "client_name",
            "source_host",
            "properties",
        ],
        {
            "id",
            "requested_at",
            "referring_domain",
            "referrer",
            "properties",
        },
    )

    assert insert_sql == (
        '"id", "partition_month", "requested_at", "referring_domain", '
        '"client_name", "source_host", "properties"'
    )
    assert 'DATE_TRUNC(\'month\', "requested_at")::date AS "partition_month"' in select_sql
    assert "NULLIF(\"properties\"->>'client_name', '') AS \"client_name\"" in select_sql
    assert "NULLIF(\"referring_domain\", '')" in select_sql
    assert "substring(\"referrer\" from '^[a-zA-Z]+://([^/]+)')" in select_sql


def test_legacy_api_usage_log_copy_prefers_existing_partition_month_column():
    _, select_sql = _build_copy_column_sql(
        ["partition_month", "source_host"],
        {"partition_month", "requested_at", "source_host", "referring_domain"},
    )

    assert (
        'COALESCE("partition_month", DATE_TRUNC(\'month\', "requested_at")::date) '
        'AS "partition_month"' in select_sql
    )
    assert (
        "COALESCE(NULLIF(\"source_host\", ''), NULLIF(\"referring_domain\", '')) "
        'AS "source_host"' in select_sql
    )


def test_legacy_api_usage_log_copy_can_skip_id_for_populated_destination():
    insert_sql, select_sql = _build_copy_column_sql(
        ["partition_month", "requested_at", "client_name"],
        {"id", "requested_at", "properties"},
    )

    assert insert_sql == '"partition_month", "requested_at", "client_name"'
    assert '"id"' not in insert_sql
    assert 'DATE_TRUNC(\'month\', "requested_at")::date AS "partition_month"' in select_sql
    assert '"requested_at" AS "requested_at"' in select_sql
    assert "NULLIF(\"properties\"->>'client_name', '') AS \"client_name\"" in select_sql
