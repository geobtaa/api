"""Recover durable daily resource counts from a complete local CSV(.gz) export.

Only resource IDs, UTC dates and counts are written. Existing conflicting counts
abort the transaction; repeat imports are safe. No raw visitor records are stored.
"""

import argparse
import csv
import gzip
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from db.migrations.analytics_storage import (
    _ensure_resource_impression_schema,
    _next_month,
    analytics_storage_engine,
)


def read_counts(path: Path, month: date, expected_count: int):
    counts = Counter()
    seen = set()
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as source:
        for row in csv.DictReader(source):
            timestamp = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone(timezone.utc)
            day = timestamp.date()
            resource_id = row["resource_id"]
            identity = (row["partition_month"], row["id"])
            if identity in seen or not resource_id or not month <= day < _next_month(month):
                raise ValueError("Duplicate, invalid resource, or out-of-month impression")
            seen.add(identity)
            counts[(day, resource_id)] += 1
    if sum(counts.values()) != expected_count:
        raise ValueError(f"Expected {expected_count} impressions; found {sum(counts.values())}")
    return counts


def save_counts(conn, counts):
    _ensure_resource_impression_schema(conn)
    conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    conn.execute(text("SELECT pg_advisory_xact_lock(7020260910)"))
    existing = conn.execute(
        text("""
        SELECT metric_date, resource_id, impression_count
        FROM analytics_daily_resource_impressions
        WHERE metric_date BETWEEN :start AND :end
    """),
        {"start": min(d for d, _ in counts), "end": max(d for d, _ in counts)},
    )
    for day, resource_id, count in existing:
        if counts.get((day, resource_id)) != count:
            raise ValueError("Recovered export conflicts with existing durable counts")
    conn.execute(
        text("""
        INSERT INTO analytics_daily_resource_impressions
            (metric_date, resource_id, impression_count)
        VALUES (:day, :resource_id, :count)
        ON CONFLICT (metric_date, resource_id) DO NOTHING
    """),
        [
            {"day": day, "resource_id": resource_id, "count": count}
            for (day, resource_id), count in counts.items()
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument(
        "--month", type=lambda value: date.fromisoformat(value + "-01"), required=True
    )
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--write", action="store_true", help="Persist verified aggregate counts")
    args = parser.parse_args()
    counts = read_counts(args.export, args.month, args.expected_count)
    if args.write:
        with analytics_storage_engine().begin() as conn:
            save_counts(conn, counts)
    print(
        f"{'Saved' if args.write else 'Verified'} {sum(counts.values())} impressions "
        f"in {len(counts)} resource/day aggregates"
    )


if __name__ == "__main__":
    main()
