"""Real PostgreSQL capture, replay, archive and expiry tests in isolated schemas."""

import json
import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.services.analytics_reporting.archive import preserve, retention_ready
from app.services.analytics_reporting.contract import SOURCES
from app.services.analytics_reporting.storage import backfill, drain, install


@pytest.fixture
def conn():
    url = os.getenv("ANALYTICS_TEST_DATABASE_URL")
    if not url:
        if os.getenv("CI", "").lower() == "true":
            pytest.fail("CI must configure ANALYTICS_TEST_DATABASE_URL")
        pytest.skip("Requires isolated analytics PostgreSQL")
    engine = create_engine(url)
    schema = "reporting_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        for source, timestamp in SOURCES.items():
            connection.execute(
                text(f'''CREATE TABLE "{source}" (
                id bigint,partition_month date NOT NULL,"{timestamp}" timestamp NOT NULL,
                visit_token text,query text,search_url text,resource_id text,
                event_type text,results_count integer,zero_results boolean,
                response_time_ms integer,PRIMARY KEY(partition_month,id)
            ) PARTITION BY RANGE(partition_month)''')
            )
            connection.execute(
                text(f'''CREATE TABLE "{source}_p202607"
                PARTITION OF "{source}" FOR VALUES FROM ('2026-07-01') TO ('2026-08-01')''')
            )
        install(connection)
        yield connection
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


class MemoryArchive:
    def __init__(self, identity):
        self.identity, self.objects, self.corrupt = identity, {}, False

    def validate(self):
        pass

    def put(self, key, body):
        if key in self.objects:
            assert self.objects[key] == body
        self.objects[key] = body

    def read(self, key):
        return b"corrupt" if self.corrupt else self.objects[key]


def insert(conn, identity=1):
    conn.execute(
        text("""INSERT INTO analytics_searches
        (id,partition_month,occurred_at,visit_token,query,search_url,results_count,zero_results)
        VALUES(:id,'2026-07-01','2026-07-31 23:59:59','private-token','water',
        '/search?q=water&page=1&secret=private',0,true) ON CONFLICT DO NOTHING"""),
        {"id": identity},
    )


def test_capture_replay_and_erase(conn):
    insert(conn)
    insert(conn)
    assert drain(conn) == 1
    assert drain(conn) == 0
    assert backfill(conn, "analytics_searches", date(2026, 7, 1)) == 0
    assert conn.execute(text("SELECT payload FROM analytics_reporting_outbox")).scalar() is None
    aggregate = conn.execute(text("SELECT metrics FROM analytics_reporting_daily")).scalar()
    assert aggregate["count"] == 1
    assert aggregate["zeroResults"] == 1
    persisted = conn.execute(text("SELECT dimensions FROM analytics_reporting_daily")).scalar()
    assert "private" not in json.dumps(persisted)


def test_rollback_does_not_accept_capture(conn):
    transaction = conn.begin_nested()
    insert(conn)
    transaction.rollback()
    assert drain(conn) == 0
    assert conn.execute(text("SELECT count(*) FROM analytics_searches")).scalar() == 0


def test_archive_late_records_and_expiry(conn):
    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]
    month = date(2026, 7, 1)
    insert(conn)
    assert not retention_ready(conn, "analytics_searches", month, archives)
    drain(conn)
    original = preserve(conn, month, archives)
    assert retention_ready(conn, "analytics_searches", month, archives)
    insert(conn, 2)
    assert not retention_ready(conn, "analytics_searches", month, archives)
    drain(conn)
    revised = preserve(conn, month, archives)
    assert revised["generation"] > original["generation"]
    assert len(archives[0].objects) == 2
    assert retention_ready(conn, "analytics_searches", month, archives)
    conn.execute(text("DROP TABLE analytics_searches_p202607"))
    assert sum(r["metrics"]["count"] for r in revised["daily"]) == 2
    assert preserve(conn, month, archives) == revised
    archives[1].corrupt = True
    assert not retention_ready(conn, "analytics_searches", month, archives)


def test_missing_capture_blocks_deletion(conn):
    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]
    month = date(2026, 7, 1)
    insert(conn)
    drain(conn)
    preserve(conn, month, archives)
    conn.execute(text("ALTER TABLE analytics_searches DISABLE TRIGGER reporting_capture"))
    insert(conn, 2)
    assert not retention_ready(conn, "analytics_searches", month, archives)


def test_rebuild_clean_reporting_database_from_recovery_copy(conn):
    from app.services.analytics_reporting.archive import month_document, restore
    from app.services.analytics_reporting.storage import checksum

    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]
    insert(conn)
    drain(conn)
    original = preserve(conn, date(2026, 7, 1), archives)
    recovered = json.loads(next(iter(archives[1].objects.values())))
    conn.execute(text("DROP TABLE analytics_searches_p202607"))
    for table in ("outbox", "daily", "visits", "months", "archives"):
        conn.execute(text(f"DELETE FROM analytics_reporting_{table}"))
    restore(conn, recovered, checksum(original))
    assert checksum(month_document(conn, date(2026, 7, 1))) == checksum(original)
    with pytest.raises(ValueError, match="already contains"):
        restore(conn, recovered, checksum(original))


def test_corrupt_attribution_cannot_be_archived(conn):
    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]
    insert(conn)
    drain(conn)
    conn.execute(text("UPDATE analytics_reporting_daily SET dimension_key='wrong'"))
    with pytest.raises(ValueError, match="dimension"):
        preserve(conn, date(2026, 7, 1), archives)
    assert not archives[0].objects


def test_source_mutation_cannot_silently_change_published_history(conn):
    insert(conn)
    drain(conn)
    with pytest.raises(Exception, match="Reporting source identity changed"):
        with conn.begin_nested():
            conn.execute(text("UPDATE analytics_searches SET query='changed'"))


def test_readonly_export_matches_live_capture(conn):
    from app.services.analytics_reporting.migration import export_readonly

    conn.execute(
        text("""CREATE TABLE resources(id text,dct_title_s text,schema_provider_s text,
        b1g_code_s text,publication_state text,gbl_suppressed_b boolean)""")
    )
    insert(conn)
    document = export_readonly(
        conn,
        date(2026, 7, 1),
        {source: (1 if source == "analytics_searches" else 0) for source in SOURCES},
    )
    assert document["coverage"]["complete"]
    assert document["daily"][0]["metrics"]["count"] == 1
    drain(conn)
    actual = conn.execute(text("SELECT metrics FROM analytics_reporting_daily")).scalar()
    assert actual == document["daily"][0]["metrics"]
    assert "private-token" not in json.dumps(document, default=str)


@pytest.mark.parametrize("expected_impressions,certified", [(7, True), (8, False)])
def test_legacy_impression_rollup_requires_baseline_match(conn, expected_impressions, certified):
    from app.services.analytics_reporting.migration import export_readonly

    conn.execute(
        text("""CREATE TABLE resources(id text,dct_title_s text,schema_provider_s text,
        b1g_code_s text,publication_state text,gbl_suppressed_b boolean)""")
    )
    conn.execute(
        text("""CREATE TABLE analytics_daily_resource_impressions
        (metric_date date,resource_id text,impression_count bigint)""")
    )
    conn.execute(
        text("""INSERT INTO analytics_daily_resource_impressions
        VALUES ('2026-07-03','resource-one',7)""")
    )
    document = export_readonly(
        conn,
        date(2026, 7, 1),
        {source: None for source in SOURCES},
        legacy={"summary": {"impressions": expected_impressions}},
    )
    assert not document["coverage"]["complete"]
    assert bool(document["coverage"]["aggregateSources"]) is certified
    assert document["daily"][0]["metrics"]["count"] == 7
    assert document["receipts"][0]["source_id"] < 0
    assert document["visits"] == []
