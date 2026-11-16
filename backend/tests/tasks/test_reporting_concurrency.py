"""Real committed transactions: writers racing expiry cannot escape preservation."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.services.analytics_reporting.archive import preserve, retention_ready
from app.services.analytics_reporting.contract import SOURCES
from app.services.analytics_reporting.storage import drain, install
from tests.tasks.test_reporting_storage import MemoryArchive, insert


def test_writer_committing_during_expiry_invalidates_receipt():
    url = os.getenv("ANALYTICS_TEST_DATABASE_URL")
    if not url:
        if os.getenv("CI", "").lower() == "true":
            pytest.fail("CI must configure ANALYTICS_TEST_DATABASE_URL")
        pytest.skip("Requires isolated PostgreSQL")
    engine = create_engine(url)
    schema = "reporting_race_" + uuid4().hex
    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]

    def use_schema(conn):
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(text("SET LOCAL lock_timeout='5s'"))

    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            use_schema(conn)
            for source, timestamp in SOURCES.items():
                conn.execute(
                    text(f'''CREATE TABLE "{source}" (
                    id bigint,partition_month date NOT NULL,"{timestamp}" timestamp NOT NULL,
                    visit_token text,query text,search_url text,results_count int,zero_results bool,
                    PRIMARY KEY(partition_month,id)) PARTITION BY RANGE(partition_month)''')
                )
                conn.execute(
                    text(f'''CREATE TABLE "{source}_p202607" PARTITION OF "{source}"
                    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01')''')
                )
            install(conn)
            insert(conn)
            drain(conn)
            preserve(conn, date(2026, 7, 1), archives)

        writer_inserted, allow_commit, expiry_started = Event(), Event(), Event()

        def writer():
            with engine.begin() as conn:
                use_schema(conn)
                insert(conn, 2)
                writer_inserted.set()
                assert allow_commit.wait(4)

        def expiry():
            assert writer_inserted.wait(4)
            with engine.begin() as conn:
                use_schema(conn)
                expiry_started.set()
                conn.execute(text("LOCK TABLE analytics_searches IN ACCESS EXCLUSIVE MODE"))
                return retention_ready(conn, "analytics_searches", date(2026, 7, 1), archives)

        with ThreadPoolExecutor(max_workers=2) as executor:
            write = executor.submit(writer)
            expire = executor.submit(expiry)
            assert expiry_started.wait(4)
            allow_commit.set()
            write.result(timeout=6)
            assert expire.result(timeout=6) is False
        with engine.begin() as conn:
            use_schema(conn)
            assert conn.execute(text("SELECT count(*) FROM analytics_searches")).scalar() == 2
            assert drain(conn) == 1
            preserve(conn, date(2026, 7, 1), archives)
            conn.execute(text("LOCK TABLE analytics_searches IN ACCESS EXCLUSIVE MODE"))
            assert retention_ready(conn, "analytics_searches", date(2026, 7, 1), archives)
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def reporting_engine():
    """Committed schema so independent writers exercise actual PostgreSQL locks."""
    from sqlalchemy import event

    url = os.getenv("ANALYTICS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL")
    engine = create_engine(url)
    schema = "reporting_job_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    @event.listens_for(engine, "begin")
    def settings(conn):
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(text("SET LOCAL lock_timeout='2s'"))
        conn.execute(text("SET LOCAL statement_timeout='10s'"))

    try:
        with engine.begin() as conn:
            for source, timestamp in SOURCES.items():
                conn.execute(
                    text(f'''CREATE TABLE "{source}" (
                    id bigint,partition_month date NOT NULL,"{timestamp}" timestamp NOT NULL,
                    visit_token text,query text,search_url text,results_count int,zero_results bool,
                    PRIMARY KEY(partition_month,id)) PARTITION BY RANGE(partition_month)''')
                )
                conn.execute(
                    text(f'''CREATE TABLE "{source}_p202607" PARTITION OF "{source}"
                    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01')''')
                )
            conn.execute(
                text("""CREATE TABLE resources(id text,dct_title_s text,
                schema_provider_s text,b1g_code_s text,publication_state text,
                gbl_suppressed_b boolean)""")
            )
            install(conn)
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_daily_publication_does_not_queue_trigger_ddl_behind_writer(reporting_engine, monkeypatch):
    from sqlalchemy import event

    from app.services.analytics_reporting import pipeline

    backfill_started = Event()
    statements = []
    original_backfill = pipeline.backfill_batch

    def backfill(*args):
        backfill_started.set()
        return original_backfill(*args)

    monkeypatch.setattr(pipeline, "backfill_batch", backfill)

    @event.listens_for(reporting_engine, "before_cursor_execute")
    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    # One committed row makes the month visible to backfill. Another transaction
    # holds the raw-table and capture locks while the daily job starts.
    with reporting_engine.begin() as conn:
        insert(conn)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with reporting_engine.begin() as writer:
            insert(writer, 2)
            job = executor.submit(
                pipeline.run,
                reporting_engine,
                today=date(2026, 8, 1),
                archives=[MemoryArchive("primary"), MemoryArchive("recovery")],
            )
            reached_backfill = backfill_started.wait(1)
        result = job.result(timeout=10)
    assert reached_backfill, "Daily reporting blocked on schema installation before backfill"
    assert result["throughExclusive"] == "2026-08-01"
    assert not any("DROP TRIGGER" in s or "CREATE TRIGGER" in s for s in statements)
    with reporting_engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM analytics_reporting_outbox")).scalar() == 2


def test_explicit_install_fails_fast_without_holding_reporting_locks(reporting_engine):
    from sqlalchemy.exc import OperationalError

    with reporting_engine.begin() as writer:
        insert(writer)
        with pytest.raises(OperationalError, match="could not obtain lock"):
            with reporting_engine.begin() as installer:
                install(installer)
        # The failed install neither drops capture nor prevents further writes.
        insert(writer, 2)
    with reporting_engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM analytics_reporting_outbox")).scalar() == 2
        install(conn)
        insert(conn, 3)
        assert conn.execute(text("SELECT count(*) FROM analytics_reporting_outbox")).scalar() == 3


def test_retention_does_not_wait_for_raw_locks_after_capture_lock(reporting_engine, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app.services.analytics_reporting.storage import LOCK
    from db.migrations import analytics_storage as storage

    config = next(c for c in storage.RAW_ANALYTICS_TABLES if c.table_name == "analytics_searches")
    monkeypatch.setattr(storage, "_maintenance_state_date", lambda *_: date(2026, 7, 31))
    monkeypatch.setenv(config.retention_env, "0")
    with reporting_engine.begin() as writer:
        # An insert holds the raw table lock before its capture trigger can run.
        writer.execute(text("LOCK TABLE analytics_searches IN ROW EXCLUSIVE MODE"))
        with pytest.raises(OperationalError, match="could not obtain lock"):
            with reporting_engine.begin() as retention:
                # Retention of an earlier source can already hold the global
                # capture lock. Waiting for the next source would invert the
                # writer's raw-table -> capture lock ordering.
                retention.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
                storage._drop_expired_partitions(retention, config)
        insert(writer)
    with reporting_engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM analytics_searches")).scalar() == 1
