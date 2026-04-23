import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import NullPool

from db.config import DATABASE_URL

logger = logging.getLogger(__name__)


def _sync_database_url() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def analytics_storage_engine() -> Engine:
    return create_engine(_sync_database_url(), poolclass=NullPool)


def _ident(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _month_range(start: date, end_inclusive: date) -> Iterable[date]:
    current = _month_start(start)
    final = _month_start(end_inclusive)
    while current <= final:
        yield current
        current = _next_month(current)


def _parse_month_suffix(name: str) -> date | None:
    match = re.search(r"_p(\d{6})$", name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m").date()


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    sql_type: str
    backfill_sql: str | None = None
    set_not_null: bool = False


@dataclass(frozen=True)
class RawAnalyticsTableConfig:
    table_name: str
    timestamp_column: str
    retention_env: str
    retention_days: int
    rollup_job_name: str
    extra_columns: Tuple[ColumnSpec, ...]
    unique_constraints: Tuple[Tuple[str, Tuple[str, ...]], ...]
    indexes: Tuple[Tuple[str, Tuple[str, ...]], ...]


RAW_ANALYTICS_TABLES: Tuple[RawAnalyticsTableConfig, ...] = (
    RawAnalyticsTableConfig(
        table_name="analytics_api_usage_logs",
        timestamp_column="requested_at",
        retention_env="ANALYTICS_RETENTION_API_USAGE_DAYS",
        retention_days=30,
        rollup_job_name="analytics_api_usage_rollup",
        extra_columns=(
            ColumnSpec(
                "partition_month",
                "DATE",
                "DATE_TRUNC('month', requested_at)::date",
                True,
            ),
            ColumnSpec(
                "client_name",
                "VARCHAR(100)",
                "NULLIF(properties->>'client_name', '')",
            ),
            ColumnSpec(
                "client_version",
                "VARCHAR(100)",
                "NULLIF(properties->>'client_version', '')",
            ),
            ColumnSpec(
                "client_channel",
                "VARCHAR(50)",
                "NULLIF(properties->>'client_channel', '')",
            ),
            ColumnSpec(
                "client_instance",
                "VARCHAR(100)",
                "NULLIF(properties->>'client_instance', '')",
            ),
            ColumnSpec(
                "source_host",
                "VARCHAR(255)",
                """
                COALESCE(
                    NULLIF(source_host, ''),
                    NULLIF(referring_domain, ''),
                    NULLIF(substring(properties->>'origin' from '^[a-zA-Z]+://([^/]+)'), '')
                )
                """,
            ),
        ),
        unique_constraints=(),
        indexes=(
            ("ix_analytics_api_usage_logs_api_key_id", ("api_key_id",)),
            ("ix_analytics_api_usage_logs_tier_id", ("tier_id",)),
            ("ix_analytics_api_usage_logs_visit_token", ("visit_token",)),
            ("ix_analytics_api_usage_logs_requested_at", ("requested_at",)),
        ),
    ),
    RawAnalyticsTableConfig(
        table_name="analytics_searches",
        timestamp_column="occurred_at",
        retention_env="ANALYTICS_RETENTION_SEARCH_DAYS",
        retention_days=90,
        rollup_job_name="analytics_search_rollup",
        extra_columns=(
            ColumnSpec(
                "partition_month",
                "DATE",
                "DATE_TRUNC('month', occurred_at)::date",
                True,
            ),
        ),
        unique_constraints=(
            ("uq_analytics_searches_identity", ("search_id", "partition_month")),
        ),
        indexes=(
            ("ix_analytics_searches_visit_token", ("visit_token",)),
            ("ix_analytics_searches_occurred_at", ("occurred_at",)),
            ("ix_analytics_searches_zero_results", ("zero_results",)),
        ),
    ),
    RawAnalyticsTableConfig(
        table_name="analytics_search_impressions",
        timestamp_column="occurred_at",
        retention_env="ANALYTICS_RETENTION_IMPRESSION_DAYS",
        retention_days=30,
        rollup_job_name="analytics_search_rollup",
        extra_columns=(
            ColumnSpec(
                "partition_month",
                "DATE",
                "DATE_TRUNC('month', occurred_at)::date",
                True,
            ),
        ),
        unique_constraints=(
            (
                "uq_analytics_search_impressions_identity",
                ("search_id", "resource_id", "rank", "page", "view", "partition_month"),
            ),
        ),
        indexes=(
            ("ix_analytics_search_impressions_resource_id", ("resource_id",)),
            ("ix_analytics_search_impressions_occurred_at", ("occurred_at",)),
        ),
    ),
    RawAnalyticsTableConfig(
        table_name="analytics_events",
        timestamp_column="occurred_at",
        retention_env="ANALYTICS_RETENTION_EVENT_DAYS",
        retention_days=90,
        rollup_job_name="analytics_resource_rollup",
        extra_columns=(
            ColumnSpec(
                "partition_month",
                "DATE",
                "DATE_TRUNC('month', occurred_at)::date",
                True,
            ),
        ),
        unique_constraints=(
            ("uq_analytics_events_identity", ("event_id", "partition_month")),
        ),
        indexes=(
            ("ix_analytics_events_event_type", ("event_type",)),
            ("ix_analytics_events_visit_token", ("visit_token",)),
            ("ix_analytics_events_search_id", ("search_id",)),
            ("ix_analytics_events_resource_id", ("resource_id",)),
            ("ix_analytics_events_occurred_at", ("occurred_at",)),
        ),
    ),
)


def _table_exists(conn: Connection, table_name: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:name)"), {"name": f"public.{table_name}"}).scalar())


def _sequence_exists(conn: Connection, sequence_name: str) -> bool:
    return bool(
        conn.execute(text("SELECT to_regclass(:name)"), {"name": f"public.{sequence_name}"}).scalar()
    )


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
    )


def _constraint_exists(conn: Connection, table_name: str, constraint_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND constraint_name = :constraint_name
                """
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).scalar()
    )


def _index_exists(conn: Connection, index_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = :index_name
                """
            ),
            {"index_name": index_name},
        ).scalar()
    )


def _is_partitioned(conn: Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM pg_partitioned_table pt
                JOIN pg_class c ON c.oid = pt.partrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = :table_name
                """
            ),
            {"table_name": table_name},
        ).scalar()
    )


def _ensure_column(conn: Connection, table_name: str, column: ColumnSpec) -> None:
    conn.execute(
        text(
            f"ALTER TABLE {_ident(table_name)} "
            f"ADD COLUMN IF NOT EXISTS {_ident(column.name)} {column.sql_type}"
        )
    )
    if column.backfill_sql:
        conn.execute(
            text(
                f"UPDATE {_ident(table_name)} "
                f"SET {_ident(column.name)} = {column.backfill_sql} "
                f"WHERE {_ident(column.name)} IS NULL"
            )
        )
    if column.set_not_null:
        conn.execute(
            text(
                f"ALTER TABLE {_ident(table_name)} "
                f"ALTER COLUMN {_ident(column.name)} SET NOT NULL"
            )
        )


def _existing_month_span(conn: Connection, table_name: str) -> Tuple[date, date]:
    row = conn.execute(
        text(
            f"SELECT MIN(partition_month), MAX(partition_month) "
            f"FROM {_ident(table_name)}"
        )
    ).one()
    current = _month_start(date.today())
    min_month = row[0] or current
    max_month = row[1] or current
    return min_month, max_month


def _ensure_partition_parent_indexes(conn: Connection, config: RawAnalyticsTableConfig) -> None:
    for index_name, columns in config.indexes:
        if _index_exists(conn, index_name):
            continue
        rendered_columns = ", ".join(_ident(column) for column in columns)
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {_ident(index_name)} "
                f"ON {_ident(config.table_name)} ({rendered_columns})"
            )
        )


def _ensure_partition_parent_constraints(conn: Connection, config: RawAnalyticsTableConfig) -> None:
    pk_name = f"{config.table_name}_pkey"
    if not _constraint_exists(conn, config.table_name, pk_name):
        conn.execute(
            text(
                f"ALTER TABLE {_ident(config.table_name)} "
                f"ADD CONSTRAINT {_ident(pk_name)} PRIMARY KEY (id, partition_month)"
            )
        )

    for constraint_name, columns in config.unique_constraints:
        if _constraint_exists(conn, config.table_name, constraint_name):
            continue
        rendered_columns = ", ".join(_ident(column) for column in columns)
        conn.execute(
            text(
                f"ALTER TABLE {_ident(config.table_name)} "
                f"ADD CONSTRAINT {_ident(constraint_name)} UNIQUE ({rendered_columns})"
            )
        )


def _partition_name(table_name: str, month: date) -> str:
    return f"{table_name}_p{month:%Y%m}"


def _ensure_partitions_for_span(
    conn: Connection,
    table_name: str,
    start_month: date,
    end_month: date,
) -> int:
    created = 0
    for month in _month_range(start_month, end_month):
        partition_name = _partition_name(table_name, month)
        if _table_exists(conn, partition_name):
            continue
        next_month = _next_month(month)
        conn.execute(
            text(
                f"CREATE TABLE {_ident(partition_name)} "
                f"PARTITION OF {_ident(table_name)} "
                "FOR VALUES FROM (:start_month) TO (:next_month)"
            ),
            {
                "start_month": month.isoformat(),
                "next_month": next_month.isoformat(),
            },
        )
        created += 1
    return created


def _ensure_future_partitions(conn: Connection, config: RawAnalyticsTableConfig) -> int:
    history_months = max(0, int(os.getenv("ANALYTICS_PARTITION_HISTORY_MONTHS", "2")))
    future_months = max(0, int(os.getenv("ANALYTICS_PARTITION_FUTURE_MONTHS", "2")))
    retention_days = int(os.getenv(config.retention_env, str(config.retention_days)))
    current = _month_start(date.today())
    start = current
    for _ in range(history_months):
        if start.month == 1:
            start = date(start.year - 1, 12, 1)
        else:
            start = date(start.year, start.month - 1, 1)
    retention_floor = _month_start(date.today() - timedelta(days=retention_days))
    if start < retention_floor:
        start = retention_floor
    end = current
    for _ in range(future_months):
        end = _next_month(end)
    return _ensure_partitions_for_span(conn, config.table_name, start, end)


def _convert_heap_table_to_partitioned(conn: Connection, config: RawAnalyticsTableConfig) -> None:
    backup_table = f"{config.table_name}_heap_legacy"
    if _table_exists(conn, backup_table):
        raise RuntimeError(
            f"Cannot convert {config.table_name}: leftover legacy table {backup_table} exists"
        )

    logger.info("Converting %s to monthly partitions", config.table_name)
    min_month, max_month = _existing_month_span(conn, config.table_name)

    conn.execute(
        text(f"ALTER TABLE {_ident(config.table_name)} RENAME TO {_ident(backup_table)}")
    )
    conn.execute(
        text(
            f"ALTER TABLE {_ident(backup_table)} "
            f"DROP CONSTRAINT IF EXISTS {_ident(f'{config.table_name}_pkey')}"
        )
    )
    for constraint_name, _ in config.unique_constraints:
        conn.execute(
            text(
                f"ALTER TABLE {_ident(backup_table)} "
                f"DROP CONSTRAINT IF EXISTS {_ident(constraint_name)}"
            )
        )
    for index_name, _ in config.indexes:
        conn.execute(text(f"DROP INDEX IF EXISTS {_ident(index_name)}"))
    conn.execute(
        text(
            f"CREATE TABLE {_ident(config.table_name)} "
            f"(LIKE {_ident(backup_table)} INCLUDING DEFAULTS INCLUDING GENERATED INCLUDING STORAGE INCLUDING COMMENTS) "
            "PARTITION BY RANGE (partition_month)"
        )
    )
    _ensure_partition_parent_constraints(conn, config)
    _ensure_partitions_for_span(conn, config.table_name, min_month, max_month)
    _ensure_partition_parent_indexes(conn, config)
    conn.execute(
        text(
            f"INSERT INTO {_ident(config.table_name)} "
            f"SELECT * FROM {_ident(backup_table)} "
            "ORDER BY partition_month, id"
        )
    )
    sequence_name = f"{config.table_name}_id_seq"
    if _sequence_exists(conn, sequence_name):
        conn.execute(
            text(
                f"ALTER SEQUENCE {_ident(sequence_name)} "
                f"OWNED BY {_ident(config.table_name)}.id"
            )
        )
    conn.execute(text(f"DROP TABLE {_ident(backup_table)}"))


def ensure_analytics_storage_schema(engine: Engine | None = None) -> Dict[str, int]:
    own_engine = engine is None
    engine = engine or analytics_storage_engine()
    summary = {"converted_tables": 0, "created_partitions": 0}
    try:
        with engine.begin() as conn:
            for config in RAW_ANALYTICS_TABLES:
                if not _table_exists(conn, config.table_name):
                    continue
                for column in config.extra_columns:
                    _ensure_column(conn, config.table_name, column)
                if not _is_partitioned(conn, config.table_name):
                    _convert_heap_table_to_partitioned(conn, config)
                    summary["converted_tables"] += 1
                _ensure_partition_parent_indexes(conn, config)
                summary["created_partitions"] += _ensure_future_partitions(conn, config)
        return summary
    finally:
        if own_engine:
            engine.dispose()


def _maintenance_state_date(conn: Connection, job_name: str) -> date | None:
    return conn.execute(
        text(
            """
            SELECT last_processed_date
            FROM analytics_maintenance_state
            WHERE job_name = :job_name
            """
        ),
        {"job_name": job_name},
    ).scalar()


def _set_maintenance_state_date(conn: Connection, job_name: str, processed_date: date) -> None:
    conn.execute(
        text(
            """
            INSERT INTO analytics_maintenance_state (job_name, last_processed_date, updated_at)
            VALUES (:job_name, :processed_date, NOW())
            ON CONFLICT (job_name)
            DO UPDATE SET
                last_processed_date = EXCLUDED.last_processed_date,
                updated_at = NOW()
            """
        ),
        {"job_name": job_name, "processed_date": processed_date},
    )


def _first_raw_metric_date(conn: Connection, table_name: str, timestamp_column: str) -> date | None:
    return conn.execute(
        text(
            f"SELECT MIN({_ident(timestamp_column)}::date) "
            f"FROM {_ident(table_name)}"
        )
    ).scalar()


def _rollup_api_usage(conn: Connection, start_date: date, end_date: date) -> None:
    conn.execute(
        text(
            """
            INSERT INTO analytics_daily_api_usage_metrics (
                rollup_key,
                metric_date,
                endpoint,
                method,
                status_code,
                tier_id,
                api_key_id,
                client_name,
                client_channel,
                source_host,
                requests_count,
                unique_visits_count,
                avg_response_time_ms,
                updated_at
            )
            SELECT
                md5(
                    concat_ws(
                        '|',
                        requested_at::date::text,
                        endpoint,
                        method,
                        status_code::text,
                        tier_id::text,
                        COALESCE(api_key_id::text, ''),
                        COALESCE(client_name, ''),
                        COALESCE(client_channel, ''),
                        COALESCE(source_host, '')
                    )
                ) AS rollup_key,
                requested_at::date AS metric_date,
                endpoint,
                method,
                status_code,
                tier_id,
                api_key_id,
                client_name,
                client_channel,
                source_host,
                COUNT(*) AS requests_count,
                COUNT(DISTINCT visit_token) FILTER (WHERE visit_token IS NOT NULL) AS unique_visits_count,
                ROUND(AVG(response_time_ms)::numeric, 2) AS avg_response_time_ms,
                NOW() AS updated_at
            FROM analytics_api_usage_logs
            WHERE requested_at::date BETWEEN :start_date AND :end_date
            GROUP BY
                requested_at::date,
                endpoint,
                method,
                status_code,
                tier_id,
                api_key_id,
                client_name,
                client_channel,
                source_host
            ON CONFLICT (rollup_key)
            DO UPDATE SET
                requests_count = EXCLUDED.requests_count,
                unique_visits_count = EXCLUDED.unique_visits_count,
                avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                updated_at = NOW()
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    )


def _rollup_search_metrics(conn: Connection, start_date: date, end_date: date) -> None:
    conn.execute(
        text(
            """
            WITH per_search AS (
                SELECT
                    s.search_id,
                    s.partition_month,
                    s.occurred_at::date AS metric_date,
                    s.client_name,
                    s.client_channel,
                    s.source_host,
                    s.view,
                    s.search_field,
                    s.sort,
                    s.zero_results,
                    s.results_count,
                    COUNT(i.id) AS impression_count
                FROM analytics_searches s
                LEFT JOIN analytics_search_impressions i
                  ON i.search_id = s.search_id
                 AND i.partition_month = s.partition_month
                WHERE s.occurred_at::date BETWEEN :start_date AND :end_date
                GROUP BY
                    s.search_id,
                    s.partition_month,
                    s.occurred_at::date,
                    s.client_name,
                    s.client_channel,
                    s.source_host,
                    s.view,
                    s.search_field,
                    s.sort,
                    s.zero_results,
                    s.results_count
            )
            INSERT INTO analytics_daily_search_metrics (
                rollup_key,
                metric_date,
                client_name,
                client_channel,
                source_host,
                view,
                search_field,
                sort,
                searches_count,
                zero_results_count,
                total_results_count,
                total_impressions_count,
                updated_at
            )
            SELECT
                md5(
                    concat_ws(
                        '|',
                        metric_date::text,
                        COALESCE(client_name, ''),
                        COALESCE(client_channel, ''),
                        COALESCE(source_host, ''),
                        COALESCE(view, ''),
                        COALESCE(search_field, ''),
                        COALESCE(sort, '')
                    )
                ) AS rollup_key,
                metric_date,
                client_name,
                client_channel,
                source_host,
                view,
                search_field,
                sort,
                COUNT(*) AS searches_count,
                SUM(CASE WHEN zero_results THEN 1 ELSE 0 END) AS zero_results_count,
                SUM(results_count) AS total_results_count,
                SUM(impression_count) AS total_impressions_count,
                NOW() AS updated_at
            FROM per_search
            GROUP BY
                metric_date,
                client_name,
                client_channel,
                source_host,
                view,
                search_field,
                sort
            ON CONFLICT (rollup_key)
            DO UPDATE SET
                searches_count = EXCLUDED.searches_count,
                zero_results_count = EXCLUDED.zero_results_count,
                total_results_count = EXCLUDED.total_results_count,
                total_impressions_count = EXCLUDED.total_impressions_count,
                updated_at = NOW()
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    )


def _rollup_resource_metrics(conn: Connection, start_date: date, end_date: date) -> None:
    conn.execute(
        text(
            """
            INSERT INTO analytics_daily_resource_metrics (
                rollup_key,
                metric_date,
                resource_id,
                event_type,
                client_name,
                client_channel,
                source_host,
                event_count,
                updated_at
            )
            SELECT
                md5(
                    concat_ws(
                        '|',
                        occurred_at::date::text,
                        COALESCE(resource_id, ''),
                        event_type,
                        COALESCE(client_name, ''),
                        COALESCE(client_channel, ''),
                        COALESCE(source_host, '')
                    )
                ) AS rollup_key,
                occurred_at::date AS metric_date,
                resource_id,
                event_type,
                client_name,
                client_channel,
                source_host,
                COUNT(*) AS event_count,
                NOW() AS updated_at
            FROM analytics_events
            WHERE occurred_at::date BETWEEN :start_date AND :end_date
              AND resource_id IS NOT NULL
            GROUP BY
                occurred_at::date,
                resource_id,
                event_type,
                client_name,
                client_channel,
                source_host
            ON CONFLICT (rollup_key)
            DO UPDATE SET
                event_count = EXCLUDED.event_count,
                updated_at = NOW()
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    )


def _rollup_job_window(
    conn: Connection,
    job_name: str,
    source_table: str,
    timestamp_column: str,
    runner,
) -> int:
    last_processed = _maintenance_state_date(conn, job_name)
    first_available = _first_raw_metric_date(conn, source_table, timestamp_column)
    if first_available is None:
        return 0

    start_date = max(first_available, last_processed + timedelta(days=1)) if last_processed else first_available
    end_date = date.today() - timedelta(days=1)
    if start_date > end_date:
        return 0

    max_days = max(1, int(os.getenv("ANALYTICS_ROLLUP_MAX_DAYS_PER_RUN", "31")))
    windows = 0
    current = start_date
    while current <= end_date:
        window_end = min(end_date, current + timedelta(days=max_days - 1))
        runner(conn, current, window_end)
        _set_maintenance_state_date(conn, job_name, window_end)
        current = window_end + timedelta(days=1)
        windows += 1
    return windows


def _drop_expired_partitions(conn: Connection, config: RawAnalyticsTableConfig) -> int:
    retention_days = int(os.getenv(config.retention_env, str(config.retention_days)))
    cutoff_date = date.today() - timedelta(days=retention_days)
    last_processed = _maintenance_state_date(conn, config.rollup_job_name)
    if last_processed is None:
        return 0

    rows = conn.execute(
        text(
            """
            SELECT child.relname
            FROM pg_inherits
            JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
            JOIN pg_class child ON child.oid = pg_inherits.inhrelid
            JOIN pg_namespace n ON n.oid = child.relnamespace
            WHERE n.nspname = 'public'
              AND parent.relname = :table_name
            ORDER BY child.relname
            """
        ),
        {"table_name": config.table_name},
    ).all()

    dropped = 0
    for (partition_name,) in rows:
        partition_month = _parse_month_suffix(partition_name)
        if partition_month is None:
            continue
        partition_end = _next_month(partition_month)
        if partition_end > cutoff_date:
            continue
        if last_processed < (partition_end - timedelta(days=1)):
            continue
        conn.execute(text(f"DROP TABLE IF EXISTS {_ident(partition_name)}"))
        dropped += 1
    return dropped


def run_analytics_maintenance(engine: Engine | None = None) -> Dict[str, int]:
    own_engine = engine is None
    engine = engine or analytics_storage_engine()
    summary = {
        "converted_tables": 0,
        "created_partitions": 0,
        "api_rollup_windows": 0,
        "search_rollup_windows": 0,
        "resource_rollup_windows": 0,
        "dropped_partitions": 0,
    }
    try:
        summary.update(ensure_analytics_storage_schema(engine))
        with engine.begin() as conn:
            summary["api_rollup_windows"] = _rollup_job_window(
                conn,
                "analytics_api_usage_rollup",
                "analytics_api_usage_logs",
                "requested_at",
                _rollup_api_usage,
            )
            summary["search_rollup_windows"] = _rollup_job_window(
                conn,
                "analytics_search_rollup",
                "analytics_searches",
                "occurred_at",
                _rollup_search_metrics,
            )
            summary["resource_rollup_windows"] = _rollup_job_window(
                conn,
                "analytics_resource_rollup",
                "analytics_events",
                "occurred_at",
                _rollup_resource_metrics,
            )
            for config in RAW_ANALYTICS_TABLES:
                summary["dropped_partitions"] += _drop_expired_partitions(conn, config)
        return summary
    finally:
        if own_engine:
            engine.dispose()


def analytics_size_report(engine: Engine | None = None) -> List[Dict[str, Any]]:
    own_engine = engine is None
    engine = engine or analytics_storage_engine()
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        c.relname AS relation_name,
                        c.relkind AS relation_kind,
                        pg_total_relation_size(c.oid) AS total_bytes,
                        pg_relation_size(c.oid) AS table_bytes,
                        pg_indexes_size(c.oid) AS index_bytes,
                        COALESCE(s.n_live_tup, 0) AS estimated_rows
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                    WHERE n.nspname = 'public'
                      AND c.relname LIKE 'analytics_%'
                      AND c.relkind IN ('r', 'p')
                    ORDER BY total_bytes DESC, relation_name
                    """
                )
            ).mappings()
            return [dict(row) for row in rows]
    finally:
        if own_engine:
            engine.dispose()
