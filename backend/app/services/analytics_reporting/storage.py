"""Transactional capture and idempotent durable reporting aggregates.

Installation is explicit. Raw-table triggers share the inserting transaction.
Outbox payloads are temporary; processing erases tokens and original query URLs.
"""

import hashlib
import json
import logging
from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy import text

from .contract import SOURCES, Visits, category, constraints, safe_text

logger = logging.getLogger(__name__)

LOCK = 7020260911
FIELDS = (
    "properties",
    "occurred_at",
    "requested_at",
    "query",
    "search_url",
    "visit_token",
    "resource_id",
    "event_type",
    "client_name",
    "client_channel",
    "view",
    "sort",
    "search_field",
    "page",
    "per_page",
    "total_pages",
    "results_count",
    "zero_results",
    "endpoint",
    "method",
    "status_code",
    "response_time_ms",
    "api_key_id",
    "tier_id",
)
DDL = """
CREATE TABLE IF NOT EXISTS analytics_reporting_deliveries (
    delivery_id text PRIMARY KEY, source_month date NOT NULL, log_id bigint
);
CREATE TABLE IF NOT EXISTS analytics_reporting_installation (
    singleton boolean PRIMARY KEY CHECK(singleton), started_at timestamptz NOT NULL);
INSERT INTO analytics_reporting_installation VALUES(true,now()) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS analytics_reporting_outbox (
    source text NOT NULL, source_month date NOT NULL, source_id bigint NOT NULL,
    payload jsonb, fingerprint text NOT NULL, captured_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz, metric_date date, dimension_key text, contribution jsonb,
    PRIMARY KEY(source, source_month, source_id)
);
CREATE INDEX IF NOT EXISTS analytics_reporting_pending
    ON analytics_reporting_outbox(source_month) WHERE processed_at IS NULL;
CREATE TABLE IF NOT EXISTS analytics_reporting_daily (
    metric_date date NOT NULL, dimension_key text NOT NULL, dimensions jsonb NOT NULL,
    metrics jsonb NOT NULL, PRIMARY KEY(metric_date, dimension_key)
);
CREATE TABLE IF NOT EXISTS analytics_reporting_visits (
    metric_date date NOT NULL, audience text NOT NULL, registers jsonb NOT NULL,
    PRIMARY KEY(metric_date, audience)
);
CREATE TABLE IF NOT EXISTS analytics_reporting_months (
    month date PRIMARY KEY, generation bigint NOT NULL DEFAULT 0,
    coverage jsonb NOT NULL DEFAULT '{}', catalog jsonb,
    catalog_captured_at timestamptz, legacy jsonb
);
CREATE TABLE IF NOT EXISTS analytics_reporting_archives (
    month date NOT NULL, generation bigint NOT NULL, checksum text NOT NULL,
    primary_key text NOT NULL, recovery_key text NOT NULL,
    verified_at timestamptz NOT NULL, restored_at timestamptz,
    PRIMARY KEY(month, generation)
);
CREATE TABLE IF NOT EXISTS analytics_reporting_publications (
    period text NOT NULL, revision text NOT NULL, document jsonb NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(period, revision)
);
CREATE TABLE IF NOT EXISTS analytics_reporting_manifest (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), document jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics_reporting_health (
    job text PRIMARY KEY, state text NOT NULL, detail text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""


def canonical(value) -> bytes:
    def encode(item):
        if isinstance(item, datetime):
            if item.tzinfo is None:
                item = item.replace(tzinfo=timezone.utc)
            return item.astimezone(timezone.utc).isoformat()
        if isinstance(item, date):
            return item.isoformat()
        raise TypeError(f"Unsupported reporting value: {type(item).__name__}")

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=encode).encode()


def checksum(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def install(conn):
    conn.execute(text(DDL))
    # Lock protocol: installation/retention take the same exclusive lock as capture.
    # This also serializes generation changes with archival receipt verification.
    keys = ",".join("'" + field + "'" for field in FIELDS)
    conn.execute(
        text(f"""
        CREATE OR REPLACE FUNCTION analytics_reporting_body(body jsonb) RETURNS jsonb
        LANGUAGE SQL IMMUTABLE AS $$
          SELECT coalesce(jsonb_object_agg(key, CASE WHEN key='properties'
            THEN jsonb_build_object('constraints',value->'constraints') ELSE value END),
            '{{}}'::jsonb) || jsonb_build_object('qgisAgent',
              position('qgis' in lower(coalesce(body->>'user_agent','')))>0)
          FROM jsonb_each(body) WHERE key IN ({keys})
        $$;
    """)
    )
    conn.execute(
        text(f"""
    CREATE OR REPLACE FUNCTION analytics_reporting_capture() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE body jsonb; changed integer; previous text;
    BEGIN
        PERFORM pg_advisory_xact_lock({LOCK});
        body := analytics_reporting_body(to_jsonb(NEW));
        INSERT INTO analytics_reporting_outbox(source,source_month,source_id,payload,fingerprint)
          VALUES(TG_ARGV[0],NEW.partition_month,NEW.id,body,md5(body::text)) ON CONFLICT DO NOTHING;
        GET DIAGNOSTICS changed = ROW_COUNT;
        IF changed = 0 THEN
          SELECT fingerprint INTO previous FROM analytics_reporting_outbox
            WHERE source=TG_ARGV[0] AND source_month=NEW.partition_month AND source_id=NEW.id;
          IF previous <> md5(body::text) THEN
            RAISE EXCEPTION 'Reporting source identity changed; use an explicit correction';
          END IF;
        END IF;
        IF changed > 0 THEN
          INSERT INTO analytics_reporting_months(month,generation)
            VALUES(NEW.partition_month,1)
            ON CONFLICT(month) DO UPDATE
              SET generation=analytics_reporting_months.generation+1;
        END IF;
        RETURN NEW;
    END $$;
    """)
    )
    for source in SOURCES:
        exists = conn.execute(text("SELECT to_regclass(:name)"), {"name": source}).scalar()
        if not exists:
            raise RuntimeError(f"Install raw analytics schema before reporting: {source}")
        conn.execute(text(f'DROP TRIGGER IF EXISTS reporting_capture ON "{source}"'))
        conn.execute(
            text(f"""CREATE TRIGGER reporting_capture AFTER INSERT OR UPDATE ON "{source}"
            FOR EACH ROW EXECUTE FUNCTION analytics_reporting_capture('{source}')""")
        )


def backfill(conn, source: str, month: date):
    """Capture available raw records, without asserting historical completeness."""
    if source not in SOURCES or month.day != 1:
        raise ValueError("Invalid source/month")
    conn.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
    count = conn.execute(
        text(f"""
        INSERT INTO analytics_reporting_outbox(source,source_month,source_id,payload,fingerprint)
        SELECT :source, r.partition_month, r.id, b.body, md5(b.body::text)
        FROM "{source}" r CROSS JOIN LATERAL
          (SELECT analytics_reporting_body(to_jsonb(r)) AS body) b
        WHERE r.partition_month=:month
        ON CONFLICT DO NOTHING
    """),
        {"source": source, "month": month},
    ).rowcount
    conn.execute(
        text("""INSERT INTO analytics_reporting_months(month,generation)
        VALUES(:month,:count) ON CONFLICT(month) DO UPDATE
        SET generation=analytics_reporting_months.generation+:count"""),
        {"month": month, "count": count},
    )
    return count


def dimensions(source, row):
    dim = {
        "source": source,
        "client": safe_text(row.get("client_name")) or "Unknown",
        "channel": safe_text(row.get("client_channel")) or "Unknown",
    }
    if source == "analytics_searches":
        query = safe_text(row.get("query"))
        saved = (row.get("properties") or {}).get("constraints") or {}
        saved = dict(saved) if isinstance(saved, dict) else {}
        for field in ("page", "per_page", "total_pages", "view", "sort", "search_field"):
            if row.get(field) is not None:
                saved[field] = row[field]
        dim.update(
            query=query,
            context=constraints(row.get("search_url"), saved),
            category=category(query),
            view=row.get("view"),
            sort=row.get("sort"),
            searchField=row.get("search_field"),
        )
    elif source in ("analytics_events", "analytics_search_impressions"):
        dim.update(resource=row.get("resource_id"), event=row.get("event_type", "impression"))
    else:
        # Endpoints are paths only; never retain arbitrary query parameters.
        endpoint = (row.get("endpoint") or "").split("?", 1)[0]
        dim.update(
            endpoint=endpoint,
            method=row.get("method"),
            status=row.get("status_code"),
            apiKey=(f"Key {row['api_key_id']}" if row.get("api_key_id") else "Anonymous"),
            tier=row.get("tier_id"),
        )
    return dim


def contribution(source, row):
    metrics = Counter()
    metrics["count"] += 1
    if source == "analytics_searches":
        metrics["zeroResults"] += int(bool(row.get("zero_results")))
        metrics["results"] += int(row.get("results_count") or 0)
        metrics[f"resultTotal:{int(row.get('results_count') or 0)}"] += 1
        if row.get("zero_results"):
            metrics[f"zeroResultTotal:{int(row.get('results_count') or 0)}"] += 1
        metrics["emptyPages"] += int((row.get("results_count") or 0) == 0)
    if source == "analytics_api_usage_logs":
        metrics["qgisUserAgentRequests"] += int(bool(row.get("qgisAgent")))
    if source == "analytics_api_usage_logs" and row.get("response_time_ms") is not None:
        duration = max(0, int(row["response_time_ms"]))
        metrics["durationSum"] += duration
        metrics["durationCount"] += 1
        # Exact integer millisecond histogram; mergeable without mean-of-means errors.
        metrics[f"latency:{duration}"] += 1
    if source != "analytics_search_impressions":
        metrics["recordsWithoutToken"] += int(not row.get("visit_token"))
    return metrics


def drain(conn, limit=2000):
    conn.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
    rows = (
        conn.execute(
            text("""SELECT * FROM analytics_reporting_outbox
        WHERE processed_at IS NULL ORDER BY source_month,source,source_id LIMIT :limit
        FOR UPDATE"""),
            {"limit": limit},
        )
        .mappings()
        .all()
    )
    grouped = {}
    sketches = {}
    contributions = []
    for record in rows:
        row, source = record["payload"], record["source"]
        timestamp = row[SOURCES[source]]
        day = date.fromisoformat(timestamp[:10])
        dim = dimensions(source, row)
        key = (day, checksum(dim))
        if key not in grouped:
            grouped[key] = (dim, Counter())
        metrics = contribution(source, row)
        audience = "api" if source == "analytics_api_usage_logs" else "discovery"
        if source != "analytics_search_impressions":
            skey = (day, audience)
            if skey not in sketches:
                saved = conn.execute(
                    text("""SELECT registers FROM analytics_reporting_visits
                    WHERE metric_date=:day AND audience=:audience"""),
                    {"day": day, "audience": audience},
                ).scalar()
                sketches[skey] = Visits(saved)
            sketches[skey].add(row.get("visit_token"))
        grouped[key][1].update(metrics)
        contributions.append(
            {**dict(record), "day": day, "key": key[1], "contribution": canonical(metrics).decode()}
        )
    for (day, key), (dim, delta) in grouped.items():
        old = conn.execute(
            text("""SELECT metrics FROM analytics_reporting_daily
            WHERE metric_date=:day AND dimension_key=:key"""),
            {"day": day, "key": key},
        ).scalar()
        merged = Counter(old or {})
        merged.update(delta)
        conn.execute(
            text("""INSERT INTO analytics_reporting_daily
            (metric_date,dimension_key,dimensions,metrics)
            VALUES(:day,:key,CAST(:dim AS jsonb),CAST(:metrics AS jsonb))
            ON CONFLICT(metric_date,dimension_key) DO UPDATE SET metrics=excluded.metrics"""),
            {
                "day": day,
                "key": key,
                "dim": canonical(dim).decode(),
                "metrics": canonical(merged).decode(),
            },
        )
    for (day, audience), sketch in sketches.items():
        conn.execute(
            text("""INSERT INTO analytics_reporting_visits VALUES
            (:day,:audience,CAST(:registers AS jsonb)) ON CONFLICT(metric_date,audience)
            DO UPDATE SET registers=excluded.registers"""),
            {"day": day, "audience": audience, "registers": json.dumps(sketch.registers)},
        )
    for record in contributions:
        conn.execute(
            text("""UPDATE analytics_reporting_outbox
            SET payload=NULL,processed_at=now(),metric_date=:day,dimension_key=:key,
                contribution=CAST(:contribution AS jsonb)
            WHERE source=:source AND source_month=:source_month AND source_id=:source_id"""),
            dict(record),
        )
    return len(rows)


def health(conn, job, state, detail):
    previous = conn.execute(
        text("SELECT state FROM analytics_reporting_health WHERE job=:job"), {"job": job}
    ).scalar()
    conn.execute(
        text("""INSERT INTO analytics_reporting_health(job,state,detail)
        VALUES(:job,:state,:detail) ON CONFLICT(job) DO UPDATE
        SET state=excluded.state,detail=excluded.detail,updated_at=now()"""),
        {"job": job, "state": state, "detail": detail},
    )

    if previous != state and (state != "healthy" or previous is not None):
        log = logger.info if state == "healthy" else logger.error
        log(
            "Analytics reporting state changed",
            extra={"reporting_job": job, "reporting_state": state, "reporting_detail": detail},
        )
