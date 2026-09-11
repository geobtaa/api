from datetime import date

import pytest

from app.services.analytics_reporting.contract import (
    Visits,
    constraints,
    next_month,
    period_bounds,
    periods,
    public_queries,
)


@pytest.mark.parametrize(
    "month,end",
    [
        ("2026-09", "2026-10-01"),
        ("2027-02", "2027-03-01"),
        ("2028-02", "2028-03-01"),
        ("2026-12", "2027-01-01"),
    ],
)
def test_calendar(month, end):
    start, actual = period_bounds(month, date(2029, 1, 1))
    assert str(actual) == end
    assert next_month(start) == actual


def test_academic_year_and_all_time_are_different():
    assert period_bounds("all", date(2028, 9, 1)) == (date(2026, 7, 1), date(2028, 9, 1))
    assert period_bounds("ay-2027", date(2028, 9, 1)) == (date(2027, 7, 1), date(2028, 7, 1))
    assert "ay-2027" in periods(date(2027, 8, 1))
    with pytest.raises(ValueError):
        period_bounds("2026-08", date(2026, 8, 1))


def test_hll_union_is_not_month_sum():
    july, august, direct = Visits(), Visits(), Visits()
    for n in range(20000):
        direct.add(str(n))
        if n < 12000:
            july.add(str(n))
        if n >= 8000:
            august.add(str(n))
    july.merge(august)
    assert july.registers == direct.registers
    assert abs(july.estimate() - 20000) / 20000 < 0.03
    july.merge(august)
    assert july.registers == direct.registers
    assert Visits().estimate() == 0


def test_query_context_privacy_and_counts():
    context = constraints("/search?q=water&token=secret&page=2&include_filters[provider]=State")
    assert context == {"page": ["2"], "include_filters[provider]": ["State"]}
    rows = [
        {"query": "water", "context": context, "count": 8, "zeroResults": 3},
        {"query": "water", "context": {"page": ["9"]}, "count": 2, "zeroResults": 2},
        {"query": "person@example.com", "context": {}, "count": 5, "zeroResults": 4},
    ]
    public = public_queries(rows)
    assert sum(r["count"] for r in public) == 15
    assert sum(r["zeroResults"] for r in public) == 9
    assert all(r["query"] != "person@example.com" for r in public)
    assert next(r for r in public if r["query"] == "Suppressed queries")["count"] == 7


def test_code_groups_do_not_confuse_federal_codes_with_universities():
    from app.services.analytics_reporting.pipeline import code_group

    assert code_group("11b-39049") == "The Ohio State University"
    assert code_group("1000-0001") == "Other"
    assert code_group("b1g_17_12385") == "BTAA-GIN curated datasets"
    assert code_group("20d-0001") == "OpenGeoMetadata"
    assert code_group(None) == "Unmapped"


@pytest.mark.parametrize(
    "month,days",
    [("2026-09", 30), ("2027-02", 28), ("2028-02", 29), ("2026-12", 31), ("2027-07", 31)],
)
def test_entire_report_generates_for_new_calendar_month_without_constants(month, days):
    from app.services.analytics_reporting.reports import build_report

    start = date.fromisoformat(month + "-01")
    document = {
        "month": str(start),
        "coverage": {"complete": True},
        "catalog": {},
        "visits": [],
        "daily": [],
    }
    report = build_report(month, next_month(start), [document])
    assert report["complete"]
    assert len(report["daily"]) == days
    assert report["daily"][-1]["date"] == f"{month}-{days}"
    assert report["daily"][-1]["views"] == 0


def test_weighted_response_times_and_saved_context_categories():
    from app.services.analytics_reporting.reports import build_report

    document = {
        "month": "2026-07-01",
        "coverage": {"complete": True},
        "catalog": {},
        "visits": [],
        "daily": [
            {
                "metric_date": "2026-07-01",
                "dimensions": {
                    "source": "analytics_api_usage_logs",
                    "client": "test",
                    "channel": "api",
                    "endpoint": "/api/v1/search",
                    "method": "GET",
                    "status": 200,
                },
                "metrics": {"count": 5, "durationSum": 50, "durationCount": 5, "latency:10": 5},
            },
            {
                "metric_date": "2026-07-02",
                "dimensions": {
                    "source": "analytics_api_usage_logs",
                    "client": "test",
                    "channel": "api",
                    "endpoint": "/api/v1/search",
                    "method": "GET",
                    "status": 200,
                },
                "metrics": {"count": 1, "durationSum": 100, "durationCount": 1, "latency:100": 1},
            },
        ],
    }
    report = build_report("2026-07", date(2026, 8, 1), [document])
    assert report["latency"] == {"meanMs": 25, "p95Ms": 100}
    assert constraints(None, {"exclude_filters[schema_provider_s][]": ["County"]}) == {
        "exclude_filters[schema_provider_s][]": ["County"]
    }


def test_legacy_counts_survive_without_inventing_combined_percentiles():
    from app.services.analytics_reporting.contract import SOURCES
    from app.services.analytics_reporting.reports import build_report

    july = {
        "month": "2026-07-01",
        "coverage": {
            "complete": False,
            "sources": {
                s: (0 if s in ("analytics_searches", "analytics_events") else None) for s in SOURCES
            },
        },
        "catalog": {},
        "visits": [],
        "daily": [],
        "legacy": {
            "summary": {
                "requests": 613131,
                "impressions": 99482,
                "serverErrors": 19,
                "p95ResponseMs": 29,
            },
            "dailyApiRequests": [{"date": "2026-07-01", "requests": 10}],
        },
    }
    august = {
        "month": "2026-08-01",
        "coverage": {"complete": True},
        "catalog": {},
        "visits": [],
        "daily": [],
    }
    monthly = build_report("2026-07", date(2026, 9, 1), [july, august])
    combined = build_report("all", date(2026, 9, 1), [july, august])
    assert monthly["totals"]["requests"] == 613131
    assert monthly["latency"]["p95Ms"] == 29
    assert combined["totals"]["requests"] == 613131
    assert combined["latency"]["p95Ms"] is None
    assert combined["totals"]["impressions"] == 99482
    assert combined["trackedVisits"]["value"] == 0


def test_search_rankings_group_terms_but_keep_failed_context_private():
    from app.services.analytics_reporting.reports import ranked_queries

    rows = [
        {
            "query": "water",
            "category": "Environment",
            "context": {"page": ["1"]},
            "count": 4,
            "zeroResults": 3,
            "resultTotals": {"0": 3, "100": 1},
            "zeroResultTotals": {"0": 3},
        },
        {
            "query": "water",
            "category": "Environment",
            "context": {"page": ["2"]},
            "count": 2,
            "zeroResults": 2,
            "resultTotals": {"0": 2},
            "zeroResultTotals": {"0": 2},
        },
        {
            "query": "roads",
            "category": "Transportation",
            "context": {},
            "count": 5,
            "zeroResults": 0,
        },
    ]
    top = ranked_queries(rows)
    assert top[0]["query"] == "water"
    assert top[0]["count"] == 6
    assert top[0]["withheldContextCount"] == 2
    failed = ranked_queries(rows, zero=True)
    assert failed[0]["count"] == 5
    assert failed[0]["resultTotals"] == {"0": 5}
    assert len(failed[0]["context"]) == 1
