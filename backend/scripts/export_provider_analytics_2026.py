"""Export checked-in provider aggregates for the July/August 2026 reports.

Read-only: retains aggregate counts and public catalog metadata, never visitor
identifiers or raw analytics records. Run against a database with complete raw
events for these months and durable daily resource impression aggregates.
Recovered exports and retained raw impressions must reconcile with monthly totals.
Historical report totals are checked before accepting an export; catalog
attribution uses the export date.
"""

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from db.migrations.analytics_storage import analytics_storage_engine

EXPECTED = {
    "2026-07": {"events": 16824, "impressions": 99482, "views": 12200, "downloads": 933},
    "2026-08": {"events": 21753, "impressions": 104455, "views": 17440, "downloads": 812},
}
ELIGIBLE = """SELECT id, dct_title_s AS title, b1g_code_s,
    CASE WHEN nullif(btrim(schema_provider_s), '') IS NULL THEN NULL
         ELSE schema_provider_s END AS provider
    FROM resources WHERE publication_state = 'published'
    AND gbl_suppressed_b IS NOT TRUE"""
METRICS = (
    """WITH eligible AS ("""
    + ELIGIBLE
    + """),
    events AS (SELECT resource_id, count(*) AS events,
      count(*) FILTER (WHERE event_type='resource_view') AS views,
      count(*) FILTER (WHERE event_type='download_click') AS downloads,
      count(*) FILTER (WHERE event_type='visit_source_click') AS sources
      FROM analytics_events WHERE occurred_at>=:start AND occurred_at<:end
      GROUP BY resource_id),
    impressions AS (SELECT resource_id, sum(impression_count) AS impressions
      FROM analytics_daily_resource_impressions WHERE metric_date>=:start AND metric_date<:end
      GROUP BY resource_id),
    metrics AS (SELECT r.*, coalesce(e.events,0) AS events,
      coalesce(e.views,0) AS views, coalesce(e.downloads,0) AS downloads,
      coalesce(e.sources,0) AS sources, coalesce(i.impressions,0) AS impressions
      FROM eligible r LEFT JOIN events e ON r.id=e.resource_id
      LEFT JOIN impressions i ON r.id=i.resource_id)
"""
)
COUNTS = """count(*) AS "catalogRecords",
    count(*) FILTER (WHERE events>0 OR impressions>0) AS "activeResources",
    sum(views) AS "resourceViews", sum(downloads) AS "downloadClicks",
    sum(sources) AS "sourceClicks", sum(impressions) AS impressions"""


def export_month(connection, month):
    start = date.fromisoformat(month + "-01")
    end = date(start.year, start.month + 1, 1)
    params = {"start": start, "end": end}

    def query(sql):
        return [dict(row) for row in connection.execute(text(sql), params).mappings()]

    observed = query("""SELECT count(*) AS events,
        count(*) FILTER (WHERE event_type='resource_view') AS views,
        count(*) FILTER (WHERE event_type='download_click') AS downloads
        FROM analytics_events WHERE occurred_at>=:start AND occurred_at<:end""")[0]
    observed["impressions"] = query("""SELECT coalesce(sum(impression_count),0) AS count
        FROM analytics_daily_resource_impressions
        WHERE metric_date>=:start AND metric_date<:end""")[0]["count"]
    impressions_available = observed["impressions"] == EXPECTED[month]["impressions"]
    events_match = all(observed[k] == EXPECTED[month][k] for k in ("events", "views", "downloads"))
    if not events_match or not impressions_available:
        raise ValueError(
            f"Incomplete or changed {month} history: {observed}; expected {EXPECTED[month]}"
        )

    groups = query(
        METRICS
        + f"SELECT provider, {COUNTS} FROM metrics GROUP BY provider ORDER BY provider NULLS LAST"
    )
    daily = query(
        """WITH eligible AS ("""
        + ELIGIBLE
        + """)
        SELECT r.provider, extract(day from e.occurred_at)::int AS day,
        count(*) FILTER (WHERE e.event_type='resource_view') AS views,
        count(*) FILTER (WHERE e.event_type='download_click') AS downloads
        FROM analytics_events e JOIN eligible r ON r.id=e.resource_id
        WHERE e.occurred_at>=:start AND e.occurred_at<:end GROUP BY r.provider, day"""
    )
    top = query(
        METRICS
        + """, ranked AS (SELECT *,
        row_number() OVER (PARTITION BY provider ORDER BY views DESC,id) AS vr,
        row_number() OVER (PARTITION BY provider ORDER BY downloads DESC,id) AS dr
        FROM metrics WHERE views>0 OR downloads>0)
        SELECT provider,id,title,views,downloads,vr,dr FROM ranked
        WHERE (vr<=3 AND views>0) OR (dr<=3 AND downloads>0)"""
    )
    for index, group in enumerate(groups):
        group["id"] = str(index)
        group["daily"] = [{"day": day, "views": 0, "downloads": 0} for day in range(1, 32)]
        for row in daily:
            if row["provider"] == group["provider"]:
                group["daily"][row["day"] - 1] = {k: row[k] for k in ("day", "views", "downloads")}
        rows = [row for row in top if row["provider"] == group["provider"]]
        group["topViews"] = [
            {k: r[k] for k in ("id", "title", "views", "downloads")}
            for r in sorted(rows, key=lambda r: r["vr"])
            if r["vr"] <= 3 and r["views"] > 0
        ]
        group["topDownloads"] = [
            {k: r[k] for k in ("id", "title", "views", "downloads")}
            for r in sorted(rows, key=lambda r: r["dr"])
            if r["dr"] <= 3 and r["downloads"] > 0
        ]
        assert sum(r["views"] for r in group["daily"]) == group["resourceViews"]
        assert sum(r["downloads"] for r in group["daily"]) == group["downloadClicks"]
    totals = query(METRICS + f"SELECT {COUNTS} FROM metrics")[0]
    coverage = query(
        METRICS
        + f"""SELECT CASE WHEN left(b1g_code_s,2) BETWEEN '01' AND '17'
        THEN 'University code 01–17' WHEN nullif(btrim(b1g_code_s),'') IS NULL
        THEN 'Missing contribution code' ELSE 'Other contribution codes' END AS label,
        {COUNTS} FROM metrics GROUP BY 1 ORDER BY 1"""
    )
    code_prefixes = query(
        METRICS
        + f"SELECT left(b1g_code_s,2) AS prefix, {COUNTS} FROM metrics GROUP BY 1 ORDER BY 1"
    )
    for key, value in totals.items():
        assert sum(g[key] for g in groups) == value
        assert sum(g[key] for g in coverage) == value
    return {
        "impressionsAvailable": True,
        "impressionSource": (
            "Recovered July export, preserved as daily resource impression aggregates."
            if month == "2026-07"
            else "Daily resource impression aggregates from retained raw records."
        ),
        "notes": [
            "Provider and code coverage use published, unsuppressed catalog records at export.",
            "Resource-level impression coverage reconciles with the original monthly total.",
            "July impressions were recovered from the complete original CSV export."
            if month == "2026-07"
            else "August impressions were aggregated from retained raw records.",
        ],
        "month": month,
        "catalogSnapshotDate": connection.execute(text("SELECT current_date")).scalar().isoformat(),
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "portalTotals": EXPECTED[month],
        "retainedRows": observed,
        "totals": totals,
        "groups": groups,
        "codeCoverage": coverage,
        "codePrefixes": code_prefixes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with analytics_storage_engine().connect() as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            connection.execute(text("SET LOCAL statement_timeout='60s'"))
            snapshots = {month: export_month(connection, month) for month in EXPECTED}
    args.output.write_text(json.dumps(snapshots, default=int, indent=2) + "\n")


if __name__ == "__main__":
    main()
