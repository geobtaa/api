import csv
import io

from scripts.export_analytics_design_data import compact_endpoint_rows
from scripts.export_analytics_snapshots import RANKINGS, preview, table_csv


def test_endpoint_display_limit_preserves_tail_errors_and_existing_remainder():
    rows = [
        {"label": f"/resource/{i:03}", "requests": 10, "errors": 1} for i in reversed(range(105))
    ]
    rows.append({"label": "Other / unlisted routes", "requests": 7, "errors": 2})
    compact = compact_endpoint_rows(rows)
    assert len(compact) == 101
    assert compact[0]["label"] == "/resource/000"
    assert compact[99]["label"] == "/resource/099"
    assert compact[-1] == {"label": "Other / unlisted routes", "requests": 57, "errors": 7}
    assert sum(row["requests"] for row in compact) == 1057
    assert sum(row["errors"] for row in compact) == 107
    assert compact_endpoint_rows(compact) == compact
    assert len(rows) == 106


def test_small_endpoint_list_has_no_invented_remainder():
    rows = [{"label": "/api/docs", "requests": 12, "errors": 0}]
    assert compact_endpoint_rows(rows) == rows
    assert compact_endpoint_rows([]) == []


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
