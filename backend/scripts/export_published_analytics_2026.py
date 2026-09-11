"""Read-only aggregates spanning the published July and August reports.

Compute rankings and distinct resource reach over the complete period, never by
adding truncated monthly rankings or distinct counts. Public metadata only.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import text

from db.migrations.analytics_storage import analytics_storage_engine
from scripts.export_provider_analytics_2026 import COUNTS, METRICS


def export_period(connection):
    params = {"start": "2026-07-01", "end": "2026-09-01"}

    def query(sql):
        return [dict(row) for row in connection.execute(text(sql), params).mappings()]

    totals = query("""SELECT count(*) AS searches,
        count(*) FILTER (WHERE zero_results) AS "zeroResults",
        count(*) FILTER (WHERE nullif(btrim(query),'') IS NOT NULL) AS "withQuery",
        count(DISTINCT btrim(query)) FILTER (WHERE nullif(btrim(query),'') IS NOT NULL)
          AS "distinctQueries"
        FROM analytics_searches WHERE occurred_at>=:start AND occurred_at<:end""")[0]
    event_total = query("""SELECT count(*) AS events FROM analytics_events
        WHERE occurred_at>=:start AND occurred_at<:end""")[0]["events"]
    if totals["searches"] != 14002 or event_total != 38577:
        raise ValueError("Published period no longer has complete source records")
    queries = query("""SELECT btrim(query) AS term,count(*) AS count FROM analytics_searches
        WHERE occurred_at>=:start AND occurred_at<:end AND nullif(btrim(query),'') IS NOT NULL
        GROUP BY btrim(query) ORDER BY count(*) DESC,btrim(query) LIMIT 50""")
    zero = query("""SELECT btrim(query) AS term,count(*) AS count FROM analytics_searches
        WHERE occurred_at>=:start AND occurred_at<:end AND zero_results
          AND nullif(btrim(query),'') IS NOT NULL
        GROUP BY btrim(query) ORDER BY count(*) DESC,btrim(query) LIMIT 100""")
    # Export per-resource impression totals from durable storage, including recovered July.
    impressions = query("""SELECT sum(impression_count) AS n
        FROM analytics_daily_resource_impressions
        WHERE metric_date>=:start AND metric_date<:end""")[0]["n"]
    if impressions != 203937:
        raise ValueError("Incomplete published impression history")
    providers = query(
        METRICS + f"SELECT provider AS label,{COUNTS} FROM metrics "
        "GROUP BY provider ORDER BY provider NULLS LAST"
    )
    codes = query(
        METRICS
        + f"""SELECT CASE WHEN left(b1g_code_s,2) BETWEEN '01' AND '17'
        THEN left(b1g_code_s,2) WHEN nullif(btrim(b1g_code_s),'') IS NULL
        THEN 'Missing contribution code' ELSE 'Other contribution codes' END AS label,
        {COUNTS} FROM metrics GROUP BY 1 ORDER BY 1"""
    )
    resources = query(
        METRICS
        + """SELECT id,title,provider,views,downloads,sources,impressions
        FROM metrics WHERE views>0 ORDER BY views DESC,id LIMIT 50"""
    )
    downloads = query(
        METRICS
        + """SELECT id,title,provider,views,downloads,sources,impressions
        FROM metrics WHERE downloads>0 ORDER BY downloads DESC,id LIMIT 50"""
    )
    views = query("""SELECT coalesce(view,'Not declared') AS label,count(*) AS count
        FROM analytics_searches WHERE occurred_at>=:start AND occurred_at<:end
        GROUP BY view ORDER BY count(*) DESC""")
    daily = query("""WITH days AS (SELECT generate_series(cast(:start AS date),
        cast(:end AS date)-1,interval '1 day')::date AS day),
        s AS (SELECT occurred_at::date AS day,count(*) AS searches,
          count(*) FILTER (WHERE zero_results) AS "zeroResults" FROM analytics_searches
          WHERE occurred_at>=:start AND occurred_at<:end GROUP BY 1),
        e AS (SELECT occurred_at::date AS day,count(*) AS events,
          count(*) FILTER (WHERE event_type='resource_view') AS views,
          count(*) FILTER (WHERE event_type='download_click') AS downloads FROM analytics_events
          WHERE occurred_at>=:start AND occurred_at<:end GROUP BY 1),
        a AS (SELECT metric_date AS day,sum(requests_count) AS requests,
          sum(requests_count) FILTER (WHERE status_code>=500) AS errors
          FROM analytics_daily_api_usage_metrics WHERE metric_date>=:start AND metric_date<:end
          GROUP BY 1)
        SELECT day,coalesce(searches,0) AS searches,coalesce("zeroResults",0) AS "zeroResults",
          coalesce(events,0) AS events,coalesce(views,0) AS views,
          coalesce(downloads,0) AS downloads,
          coalesce(requests,0) AS requests,coalesce(errors,0) AS errors
        FROM days LEFT JOIN s USING(day) LEFT JOIN e USING(day) LEFT JOIN a USING(day)
        ORDER BY day""")
    expected_totals = {
        "requests": 1212062,
        "searches": 14002,
        "events": 38577,
        "views": 29640,
        "downloads": 1745,
        "errors": 29,
    }
    if len(daily) != 62 or any(
        sum(row[key] for row in daily) != value for key, value in expected_totals.items()
    ):
        raise ValueError("Daily aggregates do not reconcile with published monthly totals")
    for key in (
        "catalogRecords",
        "activeResources",
        "resourceViews",
        "impressions",
        "downloadClicks",
        "sourceClicks",
    ):
        if sum(row[key] for row in providers) != sum(row[key] for row in codes):
            raise ValueError(f"Grouping totals disagree for {key}")
    endpoints = query("""SELECT endpoint AS label,sum(requests_count) AS requests,
        coalesce(sum(requests_count) FILTER (WHERE status_code>=500),0) AS errors
        FROM analytics_daily_api_usage_metrics WHERE metric_date>=:start AND metric_date<:end
        GROUP BY endpoint ORDER BY sum(requests_count) DESC,endpoint LIMIT 50""")
    return {
        "start": params["start"],
        "endExclusive": params["end"],
        "publishedMonths": ["2026-07", "2026-08"],
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "catalogDate": connection.execute(text("SELECT current_date")).scalar(),
        "searchTotals": totals,
        "queries": queries,
        "zeroQueries": zero,
        "providers": providers,
        "codes": codes,
        "resources": resources,
        "downloads": downloads,
        "searchViews": views,
        "daily": daily,
        "endpoints": endpoints,
    }


def main():
    with analytics_storage_engine().begin() as connection:
        connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        connection.execute(text("SET LOCAL statement_timeout='90s'"))
        result = export_period(connection)
    print(
        "PERIOD_JSON="
        + json.dumps(result, default=lambda x: x.isoformat() if hasattr(x, "isoformat") else int(x))
    )


if __name__ == "__main__":
    main()
