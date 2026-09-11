"""Daily catch-up, immutable publication, and explicit historical coverage."""

import json
import re
from datetime import date, datetime, timezone

from sqlalchemy import text

from .archive import configured_archives, preserve
from .contract import SOURCES, START, next_month, periods
from .reports import build_report
from .storage import LOCK, backfill, canonical, checksum, drain, health, install

CODE_LABELS = {
    "01": "Indiana University",
    "02": "University of Illinois",
    "03": "University of Iowa",
    "04": "University of Maryland",
    "05": "University of Minnesota",
    "06": "Michigan State University",
    "07": "University of Michigan",
    "08": "Pennsylvania State University",
    "09": "Purdue University",
    "10": "University of Wisconsin-Madison",
    "11": "The Ohio State University",
    "12": "University of Chicago",
    "13": "University of Nebraska-Lincoln",
    "14": "Rutgers University",
    "15": "Northwestern University",
    "16": "University of Washington",
    "17": "University of Oregon",
}


def code_group(code):
    code = (code or "").strip()
    if not code:
        return "Unmapped"
    if code.startswith("b1g_"):
        return "BTAA-GIN curated datasets"
    if code.startswith("20d-"):
        return "OpenGeoMetadata"
    if code.startswith("999-"):
        return "Licensed database"
    # Four-digit federal codes such as 1000-0001 are NOT university code 10.
    match = re.match(r"^(0[1-9]|1[0-7])(?:[A-Za-z-]|$)", code)
    return CODE_LABELS[match[1]] if match else "Other"


def read_catalog(conn):
    rows = conn.execute(
        text("""SELECT id,dct_title_s,schema_provider_s,b1g_code_s,
        jsonb_build_object('resourceClasses',to_jsonb(r)->'gbl_resourceClass_sm',
          'resourceTypes',to_jsonb(r)->'gbl_resourceType_sm',
          'collections',to_jsonb(r)->'pcdm_memberOf_sm',
          'format',to_jsonb(r)->'dct_format_s',
          'accessRights',to_jsonb(r)->'dct_accessRights_s') AS attributes FROM resources r
        WHERE publication_state='published' AND gbl_suppressed_b IS NOT TRUE ORDER BY id""")
    ).mappings()
    catalog = {}
    for r in rows:
        code = (r["b1g_code_s"] or "").strip()
        # Unknown codes remain explicit; no geography-based inference.
        label = code_group(code)
        catalog[r["id"]] = {
            "title": r["dct_title_s"],
            "provider": r["schema_provider_s"],
            "code": label,
            "rawCode": code,
            "attributes": r["attributes"],
        }
    return catalog


def capture_catalog(conn, month):
    current = conn.execute(
        text("SELECT catalog FROM analytics_reporting_months WHERE month=:month"), {"month": month}
    ).scalar()
    if current is not None:
        return
    catalog = read_catalog(conn)
    conn.execute(
        text("""UPDATE analytics_reporting_months SET catalog=CAST(:catalog AS jsonb),
        catalog_captured_at=now(),generation=generation+1 WHERE month=:month"""),
        {"catalog": canonical(catalog).decode(), "month": month},
    )


def publish(conn, through, documents, archives):
    """All objects are durable before the single manifest transaction becomes visible."""
    conn.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
    entries = []
    for period in periods(through):
        document = build_report(period, through, documents)
        # Partial history is explicit, never silently substituted for a complete report.
        key = f"analytics/public/v1/{period}/{document['revision']}.json"
        for archive in archives:
            archive.put(key, canonical(document))
        conn.execute(
            text("""INSERT INTO analytics_reporting_publications(period,revision,document)
            VALUES(:period,:revision,CAST(:document AS jsonb)) ON CONFLICT DO NOTHING"""),
            {
                "period": period,
                "revision": document["revision"],
                "document": canonical(document).decode(),
            },
        )
        entries.append(
            {
                "id": period,
                "revision": document["revision"],
                "complete": document["complete"],
                "start": document["start"],
                "endExclusive": document["endExclusive"],
            }
        )
    complete_months = [e["id"] for e in entries if e["complete"] and e["id"][0].isdigit()]
    manifest = {
        "schemaVersion": 1,
        "throughExclusive": str(through),
        "latest": max(complete_months) if complete_months else None,
        "periods": entries,
    }
    manifest["revision"] = checksum(manifest)
    body = canonical(manifest)
    for archive in archives:
        archive.put(f"analytics/manifests/{manifest['revision']}.json", body)
    conn.execute(
        text("""INSERT INTO analytics_reporting_manifest(singleton,document)
        VALUES(true,CAST(:document AS jsonb)) ON CONFLICT(singleton) DO UPDATE
        SET document=excluded.document"""),
        {"document": body.decode()},
    )
    return manifest


def run(engine, *, today=None, archives=None):
    today = today or datetime.now(timezone.utc).date()
    through = today.replace(day=1)
    with engine.begin() as conn:
        install(conn)
        conn.execute(
            text("""CREATE TABLE IF NOT EXISTS analytics_reporting_installation (
            singleton boolean PRIMARY KEY CHECK(singleton), started_at timestamptz NOT NULL);
            INSERT INTO analytics_reporting_installation VALUES(true,now()) ON CONFLICT DO NOTHING
        """)
        )
        started = conn.execute(
            text("SELECT started_at FROM analytics_reporting_installation")
        ).scalar()
    # Recover any inserts accepted before trigger installation or during a gap.
    # Available rows alone do not certify historical coverage.
    with engine.begin() as conn:
        for source in SOURCES:
            months = (
                conn.execute(
                    text(
                        f"SELECT DISTINCT partition_month FROM {source} "
                        "WHERE partition_month>=:start"
                    ),
                    {"start": date(2026, 7, 1)},
                )
                .scalars()
                .all()
            )
            for month in months:
                backfill(conn, source, month)
    # Bounded transactions: captured raw records remain recoverable between batches.
    while True:
        with engine.begin() as conn:
            if drain(conn) == 0:
                break
    with engine.begin() as conn:
        month = max(START, started.date().replace(day=1))
        while month < through:
            conn.execute(
                text(
                    "INSERT INTO analytics_reporting_months(month) "
                    "VALUES(:month) ON CONFLICT DO NOTHING"
                ),
                {"month": month},
            )
            month = next_month(month)
    # No closed-period changes means no re-publication or full-history archive I/O.
    with engine.begin() as conn:
        existing = conn.execute(text("SELECT document FROM analytics_reporting_manifest")).scalar()
        dirty = conn.execute(
            text("""SELECT count(*) FROM analytics_reporting_months m
            LEFT JOIN analytics_reporting_archives a
              ON a.month=m.month AND a.generation=m.generation
            WHERE m.month<:through AND a.month IS NULL"""),
            {"through": through},
        ).scalar()
        if existing and existing["throughExclusive"] == str(through) and not dirty:
            health(conn, "publication", "healthy", f"No reporting changes through {through}")
            return existing
    archives = archives or configured_archives()
    documents = []
    with engine.begin() as conn:
        months = (
            conn.execute(
                text("""SELECT month FROM analytics_reporting_months
            WHERE month<:through ORDER BY month"""),
                {"through": through},
            )
            .scalars()
            .all()
        )
    for month in months:
        with engine.begin() as conn:
            conn.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
            capture_catalog(conn, month)
            coverage = conn.execute(
                text("SELECT coverage FROM analytics_reporting_months WHERE month=:month"),
                {"month": month},
            ).scalar()
            if not coverage:
                complete = started.date().replace(day=1) <= month
                coverage = {
                    "complete": complete,
                    "basis": "current-month raw backfill and continuous transactional capture"
                    if complete
                    else "historical completeness not verified",
                }
                conn.execute(
                    text("""UPDATE analytics_reporting_months SET coverage=CAST(:coverage AS jsonb),
                    generation=generation+1 WHERE month=:month"""),
                    {"coverage": json.dumps(coverage), "month": month},
                )
            documents.append(preserve(conn, month, archives))
    with engine.begin() as conn:
        manifest = publish(conn, through, documents, archives)
        health(conn, "publication", "healthy", f"Published through {through}")
    return manifest


def import_available_history(conn, start: date, end: date):
    """Backfill available sources; verification of missing history is a separate gate."""
    month = start
    count = 0
    while month < end:
        for source in SOURCES:
            count += backfill(conn, source, month)
        month = next_month(month)
    return count
