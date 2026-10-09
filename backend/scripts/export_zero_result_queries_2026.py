"""Export top-100 July/August zero-result query aggregates, with coverage checks.

Read-only. Outputs query/count aggregates and provenance, never visitor identifiers
or raw requests. Run from backend with PYTHONPATH=. and a configured database.
"""

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from db.migrations.analytics_storage import analytics_storage_engine

EXPECTED = {
    "2026-07": {"searches": 6457, "zeroResults": 1098, "withQuery": 758, "withoutQuery": 340},
    "2026-08": {"searches": 7545, "zeroResults": 1455, "withQuery": 1148, "withoutQuery": 307},
}
SUMMARY_SQL = """SELECT count(*) AS searches,
    count(*) FILTER (WHERE zero_results) AS "zeroResults",
    count(*) FILTER (WHERE zero_results AND nullif(btrim(query), '') IS NOT NULL)
        AS "withQuery",
    count(*) FILTER (WHERE zero_results AND nullif(btrim(query), '') IS NULL)
        AS "withoutQuery",
    count(DISTINCT btrim(query)) FILTER
        (WHERE zero_results AND nullif(btrim(query), '') IS NOT NULL) AS "distinctQueries"
    FROM analytics_searches WHERE occurred_at >= :start AND occurred_at < :end"""
RANKING_SQL = """SELECT btrim(query) AS term, count(*) AS count
    FROM analytics_searches
    WHERE occurred_at >= :start AND occurred_at < :end
      AND zero_results AND nullif(btrim(query), '') IS NOT NULL
    GROUP BY btrim(query) ORDER BY count(*) DESC, btrim(query) ASC LIMIT 100"""


def export_month(connection, month):
    start = date.fromisoformat(month + "-01")
    end = date(start.year, start.month + 1, 1)
    params = {"start": start, "end": end}
    summary = dict(connection.execute(text(SUMMARY_SQL), params).mappings().one())
    if any(summary[key] != value for key, value in EXPECTED[month].items()):
        raise ValueError(f"Incomplete or changed {month} search history: {summary}")
    queries = [dict(row) for row in connection.execute(text(RANKING_SQL), params).mappings()]
    if len(queries) != min(100, summary["distinctQueries"]):
        raise ValueError(f"Incomplete {month} ranking")
    return {
        "periodStart": start.isoformat(),
        "periodEndExclusive": end.isoformat(),
        **summary,
        "rankedZeroResults": sum(row["count"] for row in queries),
        "zeroQueries": queries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    engine = analytics_storage_engine()
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            result = {
                "exportedAt": datetime.now(timezone.utc).isoformat(),
                "source": "analytics_searches",
                "rankingLimit": 100,
                "minimumZeroResults": 1,
                "grouping": "Trimmed non-empty query, case preserved",
                "ordering": "Zero-result count descending, query ascending (database collation)",
                "months": {month: export_month(connection, month) for month in EXPECTED},
            }
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
