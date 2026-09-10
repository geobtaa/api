"""Export complete top-50 monthly search-query rankings as public aggregates.

Read-only. Counts all recorded searches with non-empty trimmed query text,
retaining case and combining search filters/views. No visitor identifiers.
"""

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from db.migrations.analytics_storage import analytics_storage_engine

EXPECTED = {"2026-07": 6457, "2026-08": 7545}


def export_month(connection, month):
    start = date.fromisoformat(month + "-01")
    end = date(start.year, start.month + 1, 1)
    params = {"start": start, "end": end}
    summary = dict(
        connection.execute(
            text("""
        SELECT count(*) AS searches,
          count(*) FILTER (WHERE nullif(btrim(query),'') IS NOT NULL) AS "withQuery",
          count(DISTINCT btrim(query)) FILTER (WHERE nullif(btrim(query),'') IS NOT NULL)
            AS "distinctQueries"
        FROM analytics_searches WHERE occurred_at>=:start AND occurred_at<:end
    """),
            params,
        )
        .mappings()
        .one()
    )
    if summary["searches"] != EXPECTED[month]:
        raise ValueError(f"Incomplete or changed {month} history: {summary}")
    queries = [
        dict(row)
        for row in connection.execute(
            text("""
        SELECT btrim(query) AS term, count(*) AS count FROM analytics_searches
        WHERE occurred_at>=:start AND occurred_at<:end AND nullif(btrim(query),'') IS NOT NULL
        GROUP BY btrim(query) ORDER BY count(*) DESC, btrim(query) ASC LIMIT 50
    """),
            params,
        ).mappings()
    ]
    if len(queries) != min(50, summary["distinctQueries"]):
        raise ValueError(f"Incomplete {month} ranking")
    return {**summary, "rankedSearches": sum(row["count"] for row in queries), "queries": queries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with analytics_storage_engine().connect() as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            connection.execute(text("SET LOCAL statement_timeout='60s'"))
            result = {
                "exportedAt": datetime.now(timezone.utc).isoformat(),
                "source": "analytics_searches",
                "grouping": "Trimmed non-empty query, case preserved; filters and views combined",
                "rankingLimit": 50,
                "months": {month: export_month(connection, month) for month in EXPECTED},
            }
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
