"""Fail-closed public downloads: aggregates, never visitor-controlled strings.

Keep the allowlist explicit: adding a reporting dimension must not silently make
it public. Regex screening cannot reliably distinguish names from search terms.
"""

import math
from datetime import date

from app.services.analytics_reporting.storage import checksum

PUBLIC_PRIVACY_VERSION = "2"

METRICS = frozenset(
    "downloads durationCount durationSum errors events impressions qgisUserAgentRequests "
    "recordsWithoutToken requests resultOpens searches sourceClicks views zeroResults visits "
    "otherEvents".split()
)
CATEGORIES = frozenset(
    (
        "Property and boundaries",
        "Environment",
        "Transportation",
        "Population and society",
        "Historical maps",
        "Other",
    )
)
PUBLIC_TABLES = frozenset(("daily", "comparison", "categories", "zeroCategories"))


def numbers(row, allowed):
    return {
        key: value
        for key, value in row.items()
        if key in allowed
        and (value is None or (type(value) in (int, float) and math.isfinite(value)))
    }


def calendar(value, month=False):
    parsed = date.fromisoformat(value + "-01" if month else value)
    expected = parsed.strftime("%Y-%m") if month else parsed.isoformat()
    if value != expected:
        raise ValueError("Invalid reporting date")
    return value


def public_report(report):
    """Project a report to a small, typed, non-identifying aggregate contract."""
    period = report["period"]
    if period != "all":
        if period.startswith("ay-") and len(period) == 7 and period[3:].isdigit():
            pass
        else:
            calendar(period, month=True)
    result = {
        "schemaVersion": 1,
        "calculationVersion": str(int(report["calculationVersion"])),
        "privacyVersion": PUBLIC_PRIVACY_VERSION,
        "period": period,
        "start": calendar(report["start"]),
        "endExclusive": calendar(report["endExclusive"]),
        "complete": report.get("complete") is True,
        "missingMonths": [calendar(m, month=True) for m in report.get("missingMonths", [])],
        "sources": {
            "overview": "Aggregate counts only. Visitor text and identifiers are excluded."
        },
        "totals": numbers(report.get("totals", {}), METRICS),
        "latency": numbers(report.get("latency", {}), {"meanMs", "p95Ms"}),
        "trackedVisits": numbers(
            report.get("trackedVisits", {}), {"value", "relativeStandardError"}
        ),
    }
    result.update(numbers(report, {"zeroResultPercent"}))
    for table, field, month in (("daily", "date", False), ("comparison", "month", True)):
        result[table] = [
            {field: calendar(row[field], month=month), **numbers(row, METRICS)}
            for row in report.get(table, [])
        ]
    for table in ("categories", "zeroCategories"):
        result[table] = [
            {"category": row["category"], **numbers(row, {"count"})}
            for row in report.get(table, [])
            if row.get("category") in CATEGORIES
        ]
    result["revision"] = checksum(result)
    return result
