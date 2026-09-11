from datetime import date

from sqlalchemy import text

from app.services.analytics_reporting.archive import preserve
from app.services.analytics_reporting.pipeline import publish
from app.services.analytics_reporting.reports import build_report
from app.services.analytics_reporting.storage import drain
from tests.tasks.test_reporting_storage import MemoryArchive, conn, insert  # noqa: F401


def test_publication_restore_and_stable_revision(conn):  # noqa: F811
    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]
    for identity in range(1, 6):
        insert(conn, identity)
    drain(conn)
    conn.execute(
        text("UPDATE analytics_reporting_months SET coverage=CAST(:value AS jsonb)"),
        {"value": '{"complete": true}'},
    )
    document = preserve(conn, date(2026, 7, 1), archives)
    manifest = publish(conn, date(2026, 8, 1), [document], archives)
    assert manifest["latest"] == "2026-07"
    report = build_report("all", date(2026, 8, 1), [document])
    assert report["totals"]["searches"] == 5
    assert report["zeroResultPercent"] == 100
    assert report["trackedVisits"]["value"] == 1
    assert len(report["daily"]) == 31
    conn.execute(text("DROP TABLE analytics_searches_p202607"))
    assert publish(conn, date(2026, 8, 1), [document], archives) == manifest
    assert conn.execute(text("SELECT count(*) FROM analytics_reporting_publications")).scalar() == 3


def test_incomplete_history_is_not_a_complete_period(conn):  # noqa: F811
    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]
    insert(conn)
    drain(conn)
    document = preserve(conn, date(2026, 7, 1), archives)
    report = build_report("all", date(2026, 9, 1), [document])
    assert not report["complete"]
    assert report["missingMonths"] == ["2026-08"]
    assert report["trackedVisits"]["value"] is None
    assert report["queries"][0]["query"] == "Suppressed queries"


def test_next_day_scheduler_and_failed_publication_keep_previous_manifest(conn):  # noqa: F811
    from contextlib import contextmanager

    import pytest

    from app.services.analytics_reporting.pipeline import run

    class BoundEngine:
        @contextmanager
        def begin(self):
            with conn.begin_nested():
                yield conn

    conn.execute(text("UPDATE analytics_reporting_installation SET started_at='2026-06-30'"))
    conn.execute(
        text("""CREATE TABLE resources(id text,dct_title_s text,schema_provider_s text,
        b1g_code_s text,publication_state text,gbl_suppressed_b boolean)""")
    )
    archives = [MemoryArchive("primary"), MemoryArchive("recovery")]
    insert(conn)
    first = run(BoundEngine(), today=date(2026, 8, 1), archives=archives)
    assert first["latest"] == "2026-07"
    # August with no accepted activity is a real zero month, not a missing month.
    second = run(BoundEngine(), today=date(2026, 9, 1), archives=archives)
    assert second["latest"] == "2026-08"
    assert second != first

    class FailedArchive(MemoryArchive):
        def put(self, key, body):
            raise RuntimeError("Simulated storage outage")

    with pytest.raises(RuntimeError, match="outage"):
        run(
            BoundEngine(),
            today=date(2026, 10, 1),
            archives=[archives[0], FailedArchive("recovery")],
        )
    saved = conn.execute(text("SELECT document FROM analytics_reporting_manifest")).scalar()
    assert saved == second
