import csv
import io

from scripts.export_analytics_snapshots import RANKINGS, preview, table_csv


def test_preview_limits_rankings_but_keeps_distinct_member_leaders():
    report = {key: [{"id": str(n)} for n in range(150)] for key in RANKINGS}
    report.update(
        {
            "totals": {"views": 9000},
            "daily": [{"date": "2026-09-30", "views": 9000}],
            "memberResources": [
                {
                    "grouping": "code",
                    "name": "University",
                    "id": str(n),
                    "views": n,
                    "downloads": 30 - n,
                    "sourceClicks": 0,
                    "impressions": 0,
                }
                for n in range(30)
            ],
        }
    )
    compact = preview(report)
    assert compact["totals"] == report["totals"]
    assert compact["daily"] == report["daily"]
    assert len(compact["queries"]) == 100
    assert len(report["queries"]) == 150
    ids = {row["id"] for row in compact["memberResources"]}
    assert {"0", "29"} <= ids
    assert len(compact["memberResources"]) == len(ids)


def test_csv_neutralizes_formulas_and_preserves_nested_context():
    rows = [{"query": " =SUM(A1:A2)", "count": 3, "context": {"page": ["2"]}}]
    exported = list(csv.DictReader(io.StringIO(table_csv(rows))))
    assert exported[0]["query"].startswith("'")
    assert exported[0]["count"] == "3"
    assert exported[0]["context"] == '{"page": ["2"]}'
