"""Immutable archive adapters and fail-closed partition preservation checks."""

import hashlib
import json
import os
from dataclasses import dataclass

from sqlalchemy import text

from .contract import SOURCES, next_month
from .storage import LOCK, canonical, checksum


@dataclass
class S3Archive:
    client: object
    bucket: str
    identity: str

    def validate(self):
        if self.client.get_bucket_versioning(Bucket=self.bucket).get("Status") != "Enabled":
            raise RuntimeError("Reporting archive requires enabled versioning")
        public = self.client.get_public_access_block(Bucket=self.bucket)[
            "PublicAccessBlockConfiguration"
        ]
        if not all(
            public.get(k)
            for k in (
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ):
            raise RuntimeError("Reporting archive must block public access")
        try:
            rules = self.client.get_bucket_lifecycle_configuration(Bucket=self.bucket).get(
                "Rules", []
            )
        except self.client.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchLifecycleConfiguration":
                raise
            rules = []
        if any(
            r.get("Status") == "Enabled"
            and ("Expiration" in r or "NoncurrentVersionExpiration" in r)
            for r in rules
        ):
            raise RuntimeError("Reporting archives must not expire")

    def read(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        with response["Body"] as stream:
            return stream.read()

    def put(self, key, body):
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
                IfNoneMatch="*",
            )
        except self.client.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] not in ("PreconditionFailed", "412"):
                raise
        if self.read(key) != body:
            raise RuntimeError("Archive checksum mismatch or immutable key conflict")


def configured_archives():
    # No local-storage fallback can authorize raw expiry.
    import boto3

    archives = []
    for role in ("PRIMARY", "RECOVERY"):
        prefix = f"ANALYTICS_ARCHIVE_{role}_"
        bucket = os.environ[prefix + "BUCKET"]
        profile = os.environ[prefix + "PROFILE"]
        session = boto3.Session(profile_name=profile)
        client = session.client("s3")
        # Compare actual bucket ownership, not merely caller credentials: two
        # profiles can both have access to the same storage account.
        identity = client.get_bucket_acl(Bucket=bucket)["Owner"]["ID"]
        archives.append(S3Archive(client, bucket, identity))
    if archives[0].identity == archives[1].identity:
        raise RuntimeError("Recovery archive must use an independent storage account")
    for archive in archives:
        archive.validate()
    return archives


def month_document(conn, month):
    from datetime import date

    month = date.fromisoformat(str(month))
    end = next_month(month)
    state = (
        conn.execute(
            text("SELECT * FROM analytics_reporting_months WHERE month=:month"), {"month": month}
        )
        .mappings()
        .one()
    )
    if conn.execute(
        text("""SELECT count(*) FROM analytics_reporting_outbox
        WHERE source_month=:month AND processed_at IS NULL"""),
        {"month": month},
    ).scalar():
        raise RuntimeError("Pending reporting capture")
    daily = [
        dict(r)
        for r in conn.execute(
            text("""SELECT * FROM analytics_reporting_daily
        WHERE metric_date>=:month AND metric_date<:end ORDER BY metric_date,dimension_key"""),
            {"month": month, "end": end},
        ).mappings()
    ]
    visits = [
        dict(r)
        for r in conn.execute(
            text("""SELECT * FROM analytics_reporting_visits
        WHERE metric_date>=:month AND metric_date<:end ORDER BY metric_date,audience"""),
            {"month": month, "end": end},
        ).mappings()
    ]
    sources = [
        dict(r)
        for r in conn.execute(
            text("""SELECT source,source_id,fingerprint,metric_date,dimension_key,contribution FROM
        analytics_reporting_outbox WHERE source_month=:month ORDER BY source,source_id"""),
            {"month": month},
        ).mappings()
    ]
    deliveries = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT delivery_id,source_month,log_id FROM analytics_reporting_deliveries "
                "WHERE source_month=:month ORDER BY delivery_id"
            ),
            {"month": month},
        ).mappings()
    ]
    return {
        "deliveries": deliveries,
        "schemaVersion": 1,
        "month": str(month),
        "generation": state["generation"],
        "coverage": state["coverage"],
        "legacy": state["legacy"],
        "catalog": state["catalog"],
        "catalogCapturedAt": state["catalog_captured_at"],
        "daily": daily,
        "visits": visits,
        "receipts": sources,
    }


def preserve(conn, month, archives):
    if len(archives) != 2 or archives[0].identity == archives[1].identity:
        raise RuntimeError("Two independent reporting archives are required")
    conn.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
    document = month_document(conn, month)
    validate_document(document)
    digest = checksum(document)
    key = f"analytics/v1/{month}/{document['generation']}/{digest}.json"
    body = canonical(document)
    for archive in archives:
        archive.validate()
        archive.put(key, body)
        # Read and parse the recovery source, not merely trust an upload response.
        restored = json.loads(archive.read(key))
        if checksum(restored) != digest:
            raise RuntimeError("Reporting archive restore verification failed")
    verify_restore(conn, restored, digest)
    conn.execute(
        text("""INSERT INTO analytics_reporting_archives
        (month,generation,checksum,primary_key,recovery_key,verified_at,restored_at)
        VALUES(:month,:generation,:checksum,:key,:key,now(),now())
        ON CONFLICT(month,generation) DO UPDATE SET
        checksum=excluded.checksum,primary_key=excluded.primary_key,
        recovery_key=excluded.recovery_key,verified_at=now(),restored_at=now()"""),
        {"month": month, "generation": document["generation"], "checksum": digest, "key": key},
    )
    return document


def retention_ready(conn, source, month, archives=None):
    """Caller holds partition lock; any missing dependency refuses raw deletion."""
    if source not in SOURCES:
        raise ValueError("Invalid analytics source")
    if conn.execute(text("SELECT to_regclass('analytics_reporting_archives')")).scalar() is None:
        return False
    if not conn.execute(text(f"SELECT pg_try_advisory_xact_lock({LOCK})")).scalar():
        return False
    receipt = (
        conn.execute(
            text("""SELECT a.* FROM analytics_reporting_archives a
        JOIN analytics_reporting_months m ON m.month=a.month AND m.generation=a.generation
        WHERE a.month=:month AND a.restored_at IS NOT NULL"""),
            {"month": month},
        )
        .mappings()
        .first()
    )
    if not receipt:
        return False
    missing = conn.execute(
        text(f"""SELECT count(*) FROM "{source}" r
        LEFT JOIN analytics_reporting_outbox o ON o.source=:source
          AND o.source_month=r.partition_month AND o.source_id=r.id
        WHERE r.partition_month=:month AND (o.source_id IS NULL OR o.processed_at IS NULL
        OR o.fingerprint <> md5(analytics_reporting_body(to_jsonb(r))::text))"""),
        {"source": source, "month": month},
    ).scalar()
    if missing:
        return False
    document = month_document(conn, month)
    if checksum(document) != receipt["checksum"]:
        return False
    archives = archives or configured_archives()
    if len(archives) != 2 or archives[0].identity == archives[1].identity:
        return False
    for archive, field in zip(archives, ("primary_key", "recovery_key"), strict=True):
        archive.validate()
        if hashlib.sha256(archive.read(receipt[field])).hexdigest() != receipt["checksum"]:
            return False
    return True


def validate_document(document):
    """Reconcile every durable dimension against its processing receipts."""
    from collections import Counter, defaultdict
    from datetime import date

    from .contract import Visits

    if document["schemaVersion"] != 1:
        raise ValueError("Unsupported archive version")
    month = date.fromisoformat(str(document["month"]))
    end = next_month(month)
    expected = defaultdict(Counter)
    for row in document["receipts"]:
        day = str(row["metric_date"])
        if row["source"] not in SOURCES or not str(month) <= day < str(end):
            raise ValueError("Receipt outside archive bounds")
        expected[(day, row["dimension_key"])].update(row["contribution"])
    actual = {}
    for row in document["daily"]:
        key = (str(row["metric_date"]), row["dimension_key"])
        if key in actual or checksum(row["dimensions"]) != row["dimension_key"]:
            raise ValueError("Invalid or duplicate archive dimension")
        actual[key] = Counter(row["metrics"])
    if dict(expected) != actual:
        raise ValueError("Reporting dimensions do not reconcile with receipts")
    for row in document["visits"]:
        Visits(row["registers"])


def restore(conn, document, expected_checksum):
    """Restore one archived month into an empty reporting period, never overwrite it."""
    from datetime import date

    validate_document(document)
    if checksum(document) != expected_checksum:
        raise ValueError("Archive checksum mismatch")
    month = date.fromisoformat(str(document["month"]))
    conn.execute(text(f"SELECT pg_advisory_xact_lock({LOCK})"))
    if conn.execute(
        text("SELECT count(*) FROM analytics_reporting_months WHERE month=:month"), {"month": month}
    ).scalar():
        raise ValueError("Restore destination already contains this month")
    conn.execute(
        text("""INSERT INTO analytics_reporting_months
        (month,generation,coverage,catalog,catalog_captured_at,legacy)
        VALUES(:month,:generation,CAST(:coverage AS jsonb),CAST(:catalog AS jsonb),
               :captured,CAST(:legacy AS jsonb))"""),
        {
            "month": month,
            "generation": document["generation"],
            "coverage": canonical(document["coverage"]).decode(),
            "catalog": canonical(document["catalog"]).decode(),
            "captured": document["catalogCapturedAt"],
            "legacy": canonical(document.get("legacy")).decode(),
        },
    )
    for row in document["daily"]:
        conn.execute(
            text("""INSERT INTO analytics_reporting_daily VALUES
            (:day,:key,CAST(:dimensions AS jsonb),CAST(:metrics AS jsonb))"""),
            {
                "day": row["metric_date"],
                "key": row["dimension_key"],
                "dimensions": canonical(row["dimensions"]).decode(),
                "metrics": canonical(row["metrics"]).decode(),
            },
        )
    for row in document["visits"]:
        conn.execute(
            text(
                "INSERT INTO analytics_reporting_visits "
                "VALUES(:day,:audience,CAST(:registers AS jsonb))"
            ),
            {
                "day": row["metric_date"],
                "audience": row["audience"],
                "registers": canonical(row["registers"]).decode(),
            },
        )
    for row in document["receipts"]:
        conn.execute(
            text("""INSERT INTO analytics_reporting_outbox
            (source,source_month,source_id,fingerprint,metric_date,dimension_key,contribution,processed_at)
            VALUES(:source,:month,:id,:fingerprint,:day,:key,
                   CAST(:contribution AS jsonb),now())"""),
            {
                "source": row["source"],
                "month": month,
                "id": row["source_id"],
                "fingerprint": row["fingerprint"],
                "day": row["metric_date"],
                "key": row["dimension_key"],
                "contribution": canonical(row["contribution"]).decode(),
            },
        )

    for row in document.get("deliveries", []):
        conn.execute(
            text("INSERT INTO analytics_reporting_deliveries VALUES(:id,:month,:log_id)"),
            {"id": row["delivery_id"], "month": row["source_month"], "log_id": row["log_id"]},
        )


def verify_restore(conn, document, expected_checksum):
    """Automated restore drill in a disposable schema, before authorizing expiration."""
    from uuid import uuid4

    from .storage import DDL

    schema = "reporting_restore_" + uuid4().hex
    previous = conn.execute(text("SHOW search_path")).scalar_one()
    with conn.begin_nested():
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(text(DDL))
        restore(conn, document, expected_checksum)
        restored_document = month_document(conn, document["month"])
        if checksum(restored_document) != expected_checksum:
            raise RuntimeError("Restored database does not match archive")
        conn.execute(text("SELECT set_config('search_path',:path,true)"), {"path": previous})
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
