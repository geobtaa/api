"""Export reconciled discovery outcomes, audience coverage and failed-search context.

Read-only aggregate export; no visitor identifiers or arbitrary URL parameters.
Historical baselines remain unchanged. Catalog labels use the export date.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import text

from db.migrations.analytics_storage import analytics_storage_engine

PERIODS = {
    "2026-07": ("2026-07-01", "2026-08-01", 6457, 16824),
    "2026-08": ("2026-08-01", "2026-09-01", 7545, 21753),
    "all": ("2026-07-01", "2026-09-01", 14002, 38577),
}
PUBLIC_PARAMS = {"q", "page", "per_page", "sort", "view", "search_field", "geo", "year_range"}


MEASUREMENT_DEFINITIONS = {
    "trackedVisits": (
        "Distinct nonblank tab-scoped visit tokens across searches and events; "
        "not unique people or inactivity-based sessions."
    ),
    "uniqueVisitors": {
        "status": "unavailable",
        "reason": "No persistent visitor identifier in these snapshots.",
    },
    "pageviews": {
        "status": "unavailable",
        "reason": (
            "No general page-view collection in these snapshots; recorded page_view "
            "event rows are zero, not evidence of zero pageviews."
        ),
    },
    "sourceClicks": (
        "visit_source_click events across all recorded resource IDs; not every outbound link."
    ),
    "downloads": "download_click events, not verified file transfers.",
    "searches": (
        "Rendered search result pages including pagination/filter changes. All "
        "records declare geoportal-web/browser."
    ),
    "failedSearchContext": (
        "Sanitized saved search parameters and original result totals, grouped by "
        "term and recorded combination. Counts preserve the historical "
        "zero-result flag."
    ),
}


def public_constraints(value):
    """Allow search controls and public facet constraints; drop tracking/unknown keys."""
    if not isinstance(value, dict):
        return {}
    return {
        key: val
        for key, val in sorted(value.items())
        if key in PUBLIC_PARAMS
        or re.fullmatch(r"(?:include_filters|exclude_filters|f|fq)\[[\w:.-]+\](?:\[\])?", key)
    }


def export_period(connection, bounds):
    start, end, searches_expected, events_expected = bounds
    params = {"start": start, "end": end}

    def query(sql):
        return [dict(row) for row in connection.execute(text(sql), params).mappings()]

    totals = query("""SELECT count(*) AS events,
        count(*) FILTER(WHERE event_type='visit_source_click') AS sources,
        count(*) FILTER(WHERE event_type='download_click') AS downloads,
        count(*) FILTER(WHERE event_type='resource_view') AS views,
        count(*) FILTER(WHERE event_type='page_view') AS "pageViews"
        FROM analytics_events WHERE occurred_at>=:start AND occurred_at<:end""")[0]
    search_total = query(
        "SELECT count(*) AS n FROM analytics_searches "
        "WHERE occurred_at>=:start AND occurred_at<:end"
    )[0]["n"]
    if totals["events"] != events_expected or search_total != searches_expected:
        raise ValueError("Incomplete or changed published history")
    # Tokens are tab-scoped, not persistent person IDs or inactivity-based sessions.
    audience_cte = """WITH activity AS (
      SELECT occurred_at,visit_token,client_name,client_channel FROM analytics_searches
      WHERE occurred_at>=:start AND occurred_at<:end
      UNION ALL SELECT occurred_at,visit_token,client_name,client_channel FROM analytics_events
      WHERE occurred_at>=:start AND occurred_at<:end)
    """
    audience = query(
        audience_cte
        + """SELECT count(DISTINCT nullif(visit_token,'')) AS "trackedVisits",
      count(*) FILTER(WHERE nullif(visit_token,'') IS NULL) AS "recordsWithoutToken",
      count(*) AS "activityRecords" FROM activity"""
    )[0]
    clients = query(
        audience_cte
        + """SELECT coalesce(client_name,'Not declared') AS client,
        coalesce(client_channel,'Not declared') AS channel,count(*) AS records
        FROM activity GROUP BY 1,2 ORDER BY records DESC"""
    )
    daily = query(
        audience_cte
        + """, days AS (SELECT generate_series(cast(:start AS date),cast(:end AS
        date)-1,interval '1 day')::date AS day),
      a AS (SELECT occurred_at::date AS day,count(DISTINCT nullif(visit_token,'')) AS visits
        FROM activity GROUP BY 1),
      s AS (SELECT occurred_at::date AS day,count(*) AS searches FROM analytics_searches WHERE
        occurred_at>=:start AND occurred_at<:end GROUP BY 1),
      e AS (SELECT occurred_at::date AS day,
        count(*) FILTER(WHERE event_type='visit_source_click') AS sources,
        count(*) FILTER(WHERE event_type='download_click') AS downloads,
        count(*) FILTER(WHERE event_type='resource_view') AS views
        FROM analytics_events WHERE occurred_at>=:start AND occurred_at<:end GROUP BY 1)
      SELECT day,coalesce(visits,0) AS visits,coalesce(searches,0) AS searches,
        coalesce(sources,0) AS sources,coalesce(downloads,0) AS downloads,coalesce(views,0) AS views
      FROM days LEFT JOIN a USING(day) LEFT JOIN s USING(day) LEFT JOIN e USING(day) ORDER BY day"""
    )
    rankings = {}
    for label, event_type in [("outlinks", "visit_source_click"), ("downloads", "download_click")]:
        params["event_type"] = event_type
        rankings[label] = query("""WITH ranked AS (SELECT resource_id,count(*) AS clicks
          FROM analytics_events WHERE occurred_at>=:start AND occurred_at<:end
            AND event_type=:event_type GROUP BY resource_id)
          SELECT resource_id AS id,coalesce(r.dct_title_s,resource_id,'Unattributed resource')
        AS title,
            r.schema_provider_s AS provider,clicks FROM ranked
          LEFT JOIN resources r ON r.id=ranked.resource_id ORDER BY clicks DESC,resource_id
        NULLS LAST LIMIT 50""")
    top_terms = query("""SELECT btrim(query) AS term,count(*) AS count FROM analytics_searches
      WHERE occurred_at>=:start AND occurred_at<:end AND zero_results AND
        nullif(btrim(query),'') IS NOT NULL
      GROUP BY 1 ORDER BY count(*) DESC,term LIMIT 100""")
    # Aggregate sanitized context in memory; never export tokens, IDs, hosts or raw URLs.
    context_rows = query("""SELECT coalesce(btrim(query),'') AS term,properties->'constraints'
        AS constraints,
      page,view,sort,search_field,results_count,total_pages FROM analytics_searches
      WHERE occurred_at>=:start AND occurred_at<:end AND zero_results""")
    terms = {row["term"] for row in top_terms}
    contexts = defaultdict(Counter)
    positive_total = 0
    for row in context_rows:
        if (row["results_count"] or 0) > 0:
            positive_total += 1
        if row["term"] not in terms and row["term"] != "":
            continue
        context = {
            "constraints": public_constraints(row["constraints"]),
            "page": row["page"],
            "view": row["view"],
            "sort": row["sort"],
            "searchField": row["search_field"],
            "resultsCount": row["results_count"],
            "totalPages": row["total_pages"],
        }
        contexts[row["term"]][json.dumps(context, sort_keys=True)] += 1
    detail = {
        term: [{**json.loads(context), "count": n} for context, n in counts.most_common()]
        for term, counts in contexts.items()
    }
    for term in top_terms:
        if sum(row["count"] for row in detail[term["term"]]) != term["count"]:
            raise ValueError("Query context totals disagree")
    for metric in ["sources", "downloads", "views"]:
        if sum(row[metric] for row in daily) != totals[metric]:
            raise ValueError("Daily outcomes do not reconcile")
    if sum(row["searches"] for row in daily) != searches_expected:
        raise ValueError("Daily searches do not reconcile")
    return {
        "start": start,
        "endExclusive": end,
        "searches": search_total,
        "totals": totals,
        "audience": audience,
        "clients": clients,
        "daily": daily,
        **rankings,
        "zeroResultContexts": detail,
        "zeroResultsWithPositiveTotal": positive_total,
        "zeroResults": len(context_rows),
    }


def main():
    with analytics_storage_engine().begin() as connection:
        connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        connection.execute(text("SET LOCAL statement_timeout='90s'"))
        result = {
            "measurementDefinitions": MEASUREMENT_DEFINITIONS,
            "exportedAt": datetime.now(timezone.utc).isoformat(),
            "catalogDate": connection.execute(text("SELECT current_date")).scalar(),
            "periods": {key: export_period(connection, bounds) for key, bounds in PERIODS.items()},
        }
    print(
        "OUTCOMES_JSON="
        + json.dumps(result, default=lambda x: x.isoformat() if hasattr(x, "isoformat") else int(x))
    )


if __name__ == "__main__":
    main()
