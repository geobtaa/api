"""Pure reporting primitives. No database, worker, or network dependencies."""

import hashlib
import math
import re
from collections import Counter
from datetime import date
from urllib.parse import parse_qs, urlsplit

SCHEMA_VERSION = 1
CALCULATION_VERSION = "2"
PRIVACY_VERSION = "1"
HLL_PRECISION = 14
START = date(2026, 7, 1)
SOURCES = {
    "analytics_api_usage_logs": "requested_at",
    "analytics_searches": "occurred_at",
    "analytics_search_impressions": "occurred_at",
    "analytics_events": "occurred_at",
}
# Full-match allowlist: no tracking fields or arbitrary URL parameters.
CONTROL = re.compile(
    r"(?:page|per_page|total_pages|sort|view|search_field|geo|year_range|"
    r"(?:include_filters|exclude_filters|f|fq)\[[\w:.-]+\](?:\[\])?)\Z"
)
SENSITIVE = re.compile(
    r"@|https?://|www\.|\b(?:\d[\s().+-]*){7,}\b|"
    r"\b\d+\s+\w+(?:\s+\w+)?\s+(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr)\b",
    re.I,
)


def next_month(value: date) -> date:
    return date(value.year + value.month // 12, value.month % 12 + 1, 1)


def period_bounds(period: str, through: date) -> tuple[date, date]:
    """End is exclusive; only complete months are eligible."""
    if period == "all":
        start, end = START, through
    elif re.fullmatch(r"ay-\d{4}", period):
        year = int(period[3:])
        start, end = date(year, 7, 1), min(date(year + 1, 7, 1), through)
    elif re.fullmatch(r"\d{4}-\d{2}", period):
        start = date.fromisoformat(period + "-01")
        end = next_month(start)
    else:
        raise ValueError("Unsupported period")
    if start < START or start >= end or end > through or through.day != 1:
        raise ValueError("Period is unavailable or incomplete")
    return start, end


def periods(through: date) -> list[str]:
    months = []
    cursor = START
    while cursor < through:
        months.append(cursor.strftime("%Y-%m"))
        cursor = next_month(cursor)
    years = sorted({f"ay-{int(m[:4]) - (int(m[5:]) < 7)}" for m in months})
    return months + years + (["all"] if months else [])


def safe_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    if not value or len(value) > 250 or SENSITIVE.search(value):
        return None
    return value


def constraints(url: str | None, saved=None) -> dict:
    result = {}
    recorded = parse_qs(urlsplit(url or "").query)
    if isinstance(saved, dict):
        recorded.update({k: v if isinstance(v, list) else [v] for k, v in saved.items()})
    for key, values in recorded.items():
        values = [str(v) if isinstance(v, (int, float)) else v for v in values]
        if CONTROL.fullmatch(key) and all(safe_text(v) is not None for v in values):
            result[key] = sorted(set(values))
    return result


def category(query: str | None) -> str:
    text = (query or "").lower()
    groups = (
        ("Property and boundaries", r"parcel|boundar|district|plat|property|redlin"),
        ("Environment", r"water|soil|forest|flood|fire|climate|wetland|geolog"),
        ("Transportation", r"road|rail|transport|highway|street"),
        ("Population and society", r"census|population|demograph|income|housing"),
        ("Historical maps", r"historic|sanborn|atlas|topograph"),
    )
    return next((label for label, pattern in groups if re.search(pattern, text)), "Other")


class Visits:
    """HLL p=14, SHA-256 v1; only registers survive aggregation (~0.81% RSE).

    Not a count of people. Raw tokens and per-token hashes are never serialized.
    """

    def __init__(self, registers=None):
        self.registers = list(registers) if registers is not None else [0] * (1 << HLL_PRECISION)
        if len(self.registers) != 1 << HLL_PRECISION or any(
            not isinstance(v, int) or not 0 <= v <= 65 - HLL_PRECISION for v in self.registers
        ):
            raise ValueError("Invalid visit sketch")

    def add(self, token):
        if not token:
            return
        value = int.from_bytes(hashlib.sha256(str(token).encode()).digest()[:8], "big")
        index = value >> (64 - HLL_PRECISION)
        tail = value & ((1 << (64 - HLL_PRECISION)) - 1)
        rank = (64 - HLL_PRECISION) - tail.bit_length() + 1
        self.registers[index] = max(self.registers[index], rank)

    def merge(self, other):
        self.registers = [max(a, b) for a, b in zip(self.registers, other.registers, strict=True)]
        return self

    def estimate(self):
        size = len(self.registers)
        estimate = (0.7213 / (1 + 1.079 / size)) * size**2 / sum(2.0**-r for r in self.registers)
        zeros = self.registers.count(0)
        if estimate <= 2.5 * size and zeros:
            estimate = size * math.log(size / zeros)
        return round(estimate)


def public_queries(rows: list[dict]) -> list[dict]:
    """Threshold applies to each disclosed context, not merely the parent query."""
    output = []
    suppressed = Counter()
    for row in rows:
        if row["count"] >= 3 and safe_text(row.get("query")) is not None:
            output.append(row)
        else:
            suppressed.update({"count": row["count"], "zeroResults": row.get("zeroResults", 0)})
    if suppressed["count"]:
        output.append(
            {
                "query": "Suppressed queries",
                "context": {},
                "category": "Suppressed",
                **dict(suppressed),
            }
        )
    return sorted(output, key=lambda r: (-r["count"], r["query"]))


def legacy_daily_requests(document):
    """Normalize saved display dates without changing the original legacy evidence."""
    from datetime import datetime

    month = date.fromisoformat(document["month"])
    legacy = document.get("legacy") or {}
    result = {}
    for row in legacy.get("dailyApiRequests", []):
        value = row["date"]
        try:
            day = date.fromisoformat(value)
        except ValueError:
            day = datetime.strptime(f"{value} {month.year}", "%b %d %Y").date()
        count = row["requests"]
        if not month <= day < next_month(month) or day in result:
            raise ValueError("Invalid or duplicate legacy request date")
        if type(count) is not int or count < 0:
            raise ValueError("Invalid legacy request count")
        result[day] = count
    expected = legacy.get("summary", {}).get("requests")
    if result and expected is not None and sum(result.values()) != expected:
        raise ValueError("Legacy daily requests do not reconcile with monthly total")
    return {str(day): count for day, count in sorted(result.items())}


def provider_groups(value):
    """A scalar is one Provider facet value; arrays have overlapping membership."""
    values = value if isinstance(value, list) else [value]
    groups = sorted({v.strip() for v in values if isinstance(v, str) and v.strip()})
    return groups or ["Unmapped"]
