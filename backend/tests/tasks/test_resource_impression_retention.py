"""Exercise durable impression storage against an explicitly isolated PostgreSQL DB."""

import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from db.migrations import analytics_storage as storage
from scripts.recover_resource_impressions import read_counts, save_counts


@pytest.fixture
def conn(monkeypatch):
    class ReviewDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 10)

    monkeypatch.setattr(storage, "date", ReviewDate)
    url = os.getenv("ANALYTICS_TEST_DATABASE_URL")
    if not url:
        if os.getenv("CI", "").lower() == "true":
            pytest.fail("CI must configure ANALYTICS_TEST_DATABASE_URL for retention tests")
        pytest.skip("Set ANALYTICS_TEST_DATABASE_URL to an isolated PostgreSQL database")
    engine = create_engine(url)
    schema = "impressions_test_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        storage._ensure_resource_impression_schema(connection)
        connection.execute(
            text("""CREATE TABLE analytics_search_impressions (
            id bigint, occurred_at timestamp NOT NULL, resource_id varchar(255) NOT NULL
        )""")
        )
        yield connection
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


def add_raw(conn):
    conn.execute(
        text("""INSERT INTO analytics_search_impressions VALUES
        (1, '2026-07-01 00:00:00', 'a'), (2, '2026-07-01 23:59:59', 'a'),
        (3, '2026-07-02', 'b'), (4, '2026-08-01', 'a')""")
    )


def test_rollup_is_idempotent_and_preserves_resource_days_after_raw_expiry(conn):
    add_raw(conn)
    for _ in range(2):
        storage._rollup_resource_impressions(conn, date(2026, 7, 1), date(2026, 7, 31))
    assert storage._resource_impressions_reconcile(conn, date(2026, 7, 1), date(2026, 7, 31))
    conn.execute(text("DELETE FROM analytics_search_impressions WHERE occurred_at < '2026-08-01'"))
    rows = conn.execute(
        text("""SELECT resource_id, impression_count
        FROM analytics_daily_resource_impressions ORDER BY metric_date""")
    ).all()
    assert rows == [("a", 2), ("b", 1)]


def test_reconciliation_detects_wrong_attribution_even_with_same_total(conn):
    add_raw(conn)
    storage._rollup_resource_impressions(conn, date(2026, 7, 1), date(2026, 7, 31))
    conn.execute(
        text(
            "UPDATE analytics_daily_resource_impressions SET resource_id='wrong' "
            "WHERE resource_id='a'"
        )
    )
    assert not storage._resource_impressions_reconcile(conn, date(2026, 7, 1), date(2026, 7, 31))


def test_late_impressions_are_included_in_final_rollup(conn):
    add_raw(conn)
    storage._rollup_resource_impressions(conn, date(2026, 7, 1), date(2026, 7, 31))
    conn.execute(text("INSERT INTO analytics_search_impressions VALUES (5, '2026-07-01', 'a')"))
    assert not storage._resource_impressions_reconcile(conn, date(2026, 7, 1), date(2026, 7, 31))
    storage._rollup_resource_impressions(conn, date(2026, 7, 1), date(2026, 7, 31))
    assert storage._resource_impressions_reconcile(conn, date(2026, 7, 1), date(2026, 7, 31))


def test_recovery_is_idempotent_and_rejects_conflicts(conn):
    counts = {(date(2026, 7, 1), "a"): 2}
    save_counts(conn, counts)
    save_counts(conn, counts)
    assert (
        conn.execute(
            text("SELECT sum(impression_count) FROM analytics_daily_resource_impressions")
        ).scalar()
        == 2
    )
    with pytest.raises(ValueError, match="conflicts"):
        save_counts(conn, {(date(2026, 7, 1), "a"): 3})


def test_recovery_validates_dates_duplicates_and_total(tmp_path):
    source = tmp_path / "impressions.csv"
    header = "id,partition_month,resource_id,occurred_at\n"
    row = "1,2026-07-01,a,2026-07-01 00:00:00\n"
    source.write_text(header + row)
    assert read_counts(source, date(2026, 7, 1), 1) == {(date(2026, 7, 1), "a"): 1}
    with pytest.raises(ValueError, match="Expected"):
        read_counts(source, date(2026, 7, 1), 2)
    with pytest.raises(ValueError, match="out-of-month"):
        read_counts(source, date(2026, 8, 1), 1)
    source.write_text(header + row + row)
    with pytest.raises(ValueError, match="Duplicate"):
        read_counts(source, date(2026, 7, 1), 2)


@pytest.mark.parametrize("corrupt", [False, True])
def test_retention_reconciles_before_dropping_partition(conn, monkeypatch, corrupt):
    conn.execute(text("DROP TABLE analytics_search_impressions"))
    conn.execute(
        text("""CREATE TABLE analytics_search_impressions (
        id bigint, occurred_at timestamp NOT NULL, resource_id varchar(255) NOT NULL,
        partition_month date NOT NULL
    ) PARTITION BY RANGE (partition_month)""")
    )
    conn.execute(
        text("""CREATE TABLE analytics_search_impressions_p202607
        PARTITION OF analytics_search_impressions
        FOR VALUES FROM ('2026-07-01') TO ('2026-08-01')""")
    )
    conn.execute(
        text("""INSERT INTO analytics_search_impressions
        VALUES (1, '2026-07-01', 'a', '2026-07-01')""")
    )
    monkeypatch.setenv("ANALYTICS_RETENTION_IMPRESSION_DAYS", "0")
    monkeypatch.setattr(storage, "_maintenance_state_date", lambda *args: date(2026, 8, 31))
    monkeypatch.setattr(storage, "_rollup_search_metrics", lambda *args: None)
    # This test isolates the legacy impression reconciliation. Full archive
    # authorization is exercised separately in test_reporting_storage.py.
    monkeypatch.setattr(storage, "_reporting_retention_ready", lambda *args: True)
    if corrupt:
        conn.execute(
            text("""INSERT INTO analytics_daily_resource_impressions
            (metric_date, resource_id, impression_count) VALUES ('2026-07-01', 'wrong', 1)""")
        )
    config = next(
        c for c in storage.RAW_ANALYTICS_TABLES if c.table_name == "analytics_search_impressions"
    )
    if corrupt:
        with pytest.raises(RuntimeError, match="does not reconcile"):
            storage._drop_expired_partitions(conn, config)
        assert conn.execute(text("SELECT count(*) FROM analytics_search_impressions")).scalar() == 1
    else:
        assert storage._drop_expired_partitions(conn, config) == 1
        assert conn.execute(text("SELECT count(*) FROM analytics_search_impressions")).scalar() == 0
        assert (
            conn.execute(
                text("SELECT sum(impression_count) FROM analytics_daily_resource_impressions")
            ).scalar()
            == 1
        )
