#!/usr/bin/env python3
"""Create a production PostgreSQL/ParadeDB dump and upload it to S3.

The script is designed for the Kamal cron container. It is intentionally
production-gated so dev destinations do not start producing backups just
because the cron entry exists in the shared image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urlunsplit

DEFAULT_DATABASE_NAME = "btaa_geospatial_api"
DEFAULT_PREFIX = "btaa-geospatial-api"
DEFAULT_REQUIRED_DEST = "prd"
DEFAULT_RETENTION_COUNT = 3


@dataclass(frozen=True)
class BackupConfig:
    destination: str
    bucket: str
    prefix: str
    retention_count: int
    database_url: str
    work_dir: Path
    sse: str | None = None
    sse_kms_key_id: str | None = None
    storage_class: str | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _normalize_database_url(database_url: str) -> str:
    """Convert SQLAlchemy asyncpg URLs to libpq-compatible PostgreSQL URLs."""
    split = urlsplit(database_url)
    if split.scheme == "postgresql+asyncpg":
        return urlunsplit(("postgresql", split.netloc, split.path, split.query, split.fragment))
    if split.scheme == "postgresql+psycopg2":
        return urlunsplit(("postgresql", split.netloc, split.path, split.query, split.fragment))
    return database_url


def _s3_key(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part and part.strip("/"))


def _aws_extra_upload_args(config: BackupConfig) -> list[str]:
    args: list[str] = []
    if config.sse:
        args.extend(["--sse", config.sse])
    if config.sse_kms_key_id:
        args.extend(["--sse-kms-key-id", config.sse_kms_key_id])
    if config.storage_class:
        args.extend(["--storage-class", config.storage_class])
    return args


def _run(args: list[str], *, capture_json: bool = False) -> dict[str, object] | None:
    try:
        result = subprocess.run(
            args,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or f"{args[0]} failed").strip()
        raise RuntimeError(message) from exc

    if not capture_json:
        return None
    stdout = result.stdout.strip()
    return json.loads(stdout) if stdout else {}


def _require_command(command: str) -> None:
    if not shutil.which(command):
        raise RuntimeError(f"Required command not found on PATH: {command}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_config() -> BackupConfig:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    bucket = os.getenv("BACKUP_S3_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("BACKUP_S3_BUCKET is required when backups are enabled")

    destination = os.getenv("KAMAL_DEST", "unknown").strip() or "unknown"
    prefix = os.getenv("BACKUP_S3_PREFIX", DEFAULT_PREFIX).strip("/")
    retention_count = _env_int("BACKUP_RETENTION_COUNT", DEFAULT_RETENTION_COUNT)
    if retention_count < 1:
        raise RuntimeError("BACKUP_RETENTION_COUNT must be at least 1")

    return BackupConfig(
        destination=destination,
        bucket=bucket,
        prefix=prefix,
        retention_count=retention_count,
        database_url=_normalize_database_url(database_url),
        work_dir=Path(os.getenv("BACKUP_WORK_DIR", "/tmp/btaa-geospatial-api-backups")),
        sse=os.getenv("BACKUP_S3_SSE") or None,
        sse_kms_key_id=os.getenv("BACKUP_S3_SSE_KMS_KEY_ID") or None,
        storage_class=os.getenv("BACKUP_S3_STORAGE_CLASS") or None,
    )


def _should_skip_scheduled_backup(force: bool) -> str | None:
    if force:
        return None

    if not _env_bool("BACKUP_ENABLED", default=False):
        return "BACKUP_ENABLED is not true"

    destination = os.getenv("KAMAL_DEST", "").strip()
    required = os.getenv("BACKUP_REQUIRED_DEST", DEFAULT_REQUIRED_DEST).strip()
    if required and destination != required:
        return (
            f"KAMAL_DEST={destination or '(unset)'} does not match BACKUP_REQUIRED_DEST={required}"
        )

    return None


def _create_pg_dump(config: BackupConfig, output_path: Path) -> None:
    _require_command("pg_dump")
    _require_command("pg_restore")

    _run(
        [
            "pg_dump",
            "--dbname",
            config.database_url,
            "--format",
            "custom",
            "-Z",
            "9",
            "--no-owner",
            "--no-acl",
            "--file",
            str(output_path),
        ]
    )

    # Fast archive sanity check before the artifact leaves the box.
    _run(["pg_restore", "--list", str(output_path)])


def _upload_file(config: BackupConfig, source: Path, key: str, metadata: dict[str, str]) -> None:
    _require_command("aws")

    metadata_arg = ",".join(f"{name}={value}" for name, value in metadata.items())
    command = [
        "aws",
        "s3",
        "cp",
        str(source),
        f"s3://{config.bucket}/{key}",
        "--only-show-errors",
    ]
    if metadata_arg:
        command.extend(["--metadata", metadata_arg])
    command.extend(_aws_extra_upload_args(config))
    _run(command)


def _head_object(config: BackupConfig, key: str) -> dict[str, object]:
    _require_command("aws")
    result = _run(
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            config.bucket,
            "--key",
            key,
        ],
        capture_json=True,
    )
    return result or {}


def _list_objects(config: BackupConfig, prefix: str) -> list[dict[str, object]]:
    _require_command("aws")
    objects: list[dict[str, object]] = []
    token: str | None = None

    while True:
        command = [
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            config.bucket,
            "--prefix",
            prefix,
        ]
        if token:
            command.extend(["--continuation-token", token])
        payload = _run(command, capture_json=True) or {}
        objects.extend(payload.get("Contents", []))  # type: ignore[arg-type]
        if not payload.get("IsTruncated"):
            break
        token = str(payload.get("NextContinuationToken") or "")
        if not token:
            break

    return objects


def _delete_object(config: BackupConfig, key: str) -> None:
    _run(["aws", "s3", "rm", f"s3://{config.bucket}/{key}", "--only-show-errors"])


def _prune_old_backups(config: BackupConfig, backup_prefix: str) -> list[str]:
    objects = [
        obj
        for obj in _list_objects(config, backup_prefix)
        if str(obj.get("Key", "")).endswith(".dump")
    ]
    objects.sort(key=lambda obj: str(obj.get("LastModified", "")), reverse=True)

    deleted: list[str] = []
    for obj in objects[config.retention_count :]:
        key = str(obj["Key"])
        manifest_key = f"{key}.manifest.json"
        _delete_object(config, key)
        deleted.append(key)
        _delete_object(config, manifest_key)
        deleted.append(manifest_key)

    return deleted


def create_backup(config: BackupConfig) -> dict[str, object]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{DEFAULT_DATABASE_NAME}_{config.destination}_{timestamp}.dump"
    backup_prefix = _s3_key(config.prefix, config.destination, "postgres")
    backup_key = _s3_key(backup_prefix, filename)
    manifest_key = f"{backup_key}.manifest.json"

    config.work_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="postgres-", dir=str(config.work_dir)) as tmpdir:
        dump_path = Path(tmpdir) / filename
        manifest_path = Path(tmpdir) / f"{filename}.manifest.json"

        print(f"Creating PostgreSQL dump: {filename}", flush=True)
        _create_pg_dump(config, dump_path)

        sha256 = _sha256(dump_path)
        size_bytes = dump_path.stat().st_size
        created_at = datetime.now(UTC).isoformat()

        manifest = {
            "artifact": "postgres",
            "database": DEFAULT_DATABASE_NAME,
            "destination": config.destination,
            "created_at": created_at,
            "s3_bucket": config.bucket,
            "s3_key": backup_key,
            "filename": filename,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "format": "pg_dump custom",
            "retention_count": config.retention_count,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        metadata = {
            "artifact": "postgres",
            "destination": config.destination,
            "sha256": sha256,
        }
        print(f"Uploading dump to s3://{config.bucket}/{backup_key}", flush=True)
        _upload_file(config, dump_path, backup_key, metadata)
        _upload_file(config, manifest_path, manifest_key, metadata)

        head = _head_object(config, backup_key)
        if int(head.get("ContentLength", -1)) != size_bytes:
            raise RuntimeError(
                f"S3 object size mismatch for {backup_key}: "
                f"expected={size_bytes} actual={head.get('ContentLength')}"
            )

    deleted = _prune_old_backups(config, f"{backup_prefix}/")
    print(
        f"PostgreSQL backup complete: s3://{config.bucket}/{backup_key} "
        f"(retention deleted {len(deleted)} object(s))",
        flush=True,
    )

    return {
        "backup_key": backup_key,
        "manifest_key": manifest_key,
        "deleted": deleted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up PostgreSQL/ParadeDB to S3")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when BACKUP_ENABLED/KAMAL_DEST gating would normally skip",
    )
    args = parser.parse_args()

    skip_reason = _should_skip_scheduled_backup(force=args.force)
    if skip_reason:
        print(f"Skipping PostgreSQL backup: {skip_reason}", flush=True)
        return 0

    try:
        config = _build_config()
        create_backup(config)
        return 0
    except Exception as exc:
        print(f"PostgreSQL backup failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
