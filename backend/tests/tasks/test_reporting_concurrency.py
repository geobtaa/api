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
