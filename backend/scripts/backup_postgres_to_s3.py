#!/usr/bin/env python3
"""Create a production PostgreSQL/ParadeDB dump.

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
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit, urlunsplit

DEFAULT_DATABASE_NAME = "btaa_geospatial_api"
DEFAULT_PREFIX = "btaa-geospatial-api"
DEFAULT_REQUIRED_DEST = "prd"
DEFAULT_RETENTION_COUNT = 3
LOCK_FILENAME = "postgres-backup.lock"


class BackupAlreadyRunning(RuntimeError):
    """Raised when another PostgreSQL backup process owns the lock."""


@dataclass(frozen=True)
class BackupConfig:
    destination: str
    target: str
    prefix: str
    retention_count: int
    database_url: str
    work_dir: Path
    bucket: str | None = None
    local_dir: Path | None = None
    sse: str | None = None
    sse_kms_key_id: str | None = None
    storage_class: str | None = None


@dataclass(frozen=True)
class PgConnectionArgs:
    args: list[str]
    env: dict[str, str]


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


def _pg_connection_args(database_url: str) -> PgConnectionArgs:
    split = urlsplit(database_url)
    if split.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError(f"Unsupported PostgreSQL URL scheme: {split.scheme}")

    if not split.hostname:
        raise RuntimeError("DATABASE_URL must include a hostname")

    database = unquote(split.path.lstrip("/"))
    if not database:
        raise RuntimeError("DATABASE_URL must include a database name")

    args = [
        "--host",
        split.hostname,
        "--dbname",
        database,
    ]
    if split.port:
        args.extend(["--port", str(split.port)])
    if split.username:
        args.extend(["--username", unquote(split.username)])

    env = os.environ.copy()
    if split.password:
        env["PGPASSWORD"] = unquote(split.password)

    return PgConnectionArgs(args=args, env=env)


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


def _run(
    args: list[str], *, capture_json: bool = False, env: dict[str, str] | None = None
) -> dict[str, object] | None:
    try:
        result = subprocess.run(
            args,
            check=True,
            text=True,
            capture_output=True,
            env=env,
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


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    return True


def _read_lock_pid(lock_path: Path) -> int | None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    try:
        return int(payload.get("pid"))
    except (TypeError, ValueError):
        return None


@contextmanager
def _backup_lock(config: BackupConfig):
    lock_path = config.work_dir / LOCK_FILENAME
    token = f"{os.getpid()}:{datetime.now(UTC).isoformat()}"
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "destination": config.destination,
        "pid": os.getpid(),
        "target": config.target,
        "token": token,
    }

    for _attempt in range(2):
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            existing_pid = _read_lock_pid(lock_path)
            if existing_pid is not None and _pid_is_running(existing_pid):
                raise BackupAlreadyRunning(
                    f"PostgreSQL backup already running (pid={existing_pid})"
                ) from None

            try:
                lock_path.unlink()
            except FileNotFoundError:
                # Another process removed the stale lock between our read and unlink.
                pass
            except OSError as exc:
                raise BackupAlreadyRunning(
                    f"PostgreSQL backup lock exists but cannot be removed: {lock_path}"
                ) from exc
            continue

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        except Exception:
            lock_path.unlink(missing_ok=True)
            raise
        break
    else:
        raise BackupAlreadyRunning(f"PostgreSQL backup lock exists: {lock_path}")

    try:
        yield
    finally:
        try:
            current_payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if current_payload.get("token") == token:
            lock_path.unlink(missing_ok=True)


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

    destination = os.getenv("KAMAL_DEST", "unknown").strip() or "unknown"
    target = os.getenv("BACKUP_POSTGRES_TARGET", "s3").strip().lower()
    if target not in {"local", "s3"}:
        raise RuntimeError("BACKUP_POSTGRES_TARGET must be 'local' or 's3'")

    prefix = os.getenv("BACKUP_S3_PREFIX", DEFAULT_PREFIX).strip("/")
    retention_count = _env_int("BACKUP_RETENTION_COUNT", DEFAULT_RETENTION_COUNT)
    if retention_count < 1:
        raise RuntimeError("BACKUP_RETENTION_COUNT must be at least 1")

    bucket = os.getenv("BACKUP_S3_BUCKET", "").strip() or None
    if target == "s3" and not bucket:
        raise RuntimeError("BACKUP_S3_BUCKET is required when Postgres backup target is s3")

    local_dir = Path(os.getenv("BACKUP_LOCAL_DIR", "/var/backups/btaa-geospatial-api"))
    work_dir = Path(os.getenv("BACKUP_WORK_DIR", str(local_dir / ".tmp")))

    return BackupConfig(
        destination=destination,
        target=target,
        prefix=prefix,
        retention_count=retention_count,
        database_url=_normalize_database_url(database_url),
        work_dir=work_dir,
        bucket=bucket,
        local_dir=local_dir,
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
    connection = _pg_connection_args(config.database_url)

    _run(
        [
            "pg_dump",
            *connection.args,
            "--format",
            "custom",
            "-Z",
            "9",
            "--no-owner",
            "--no-acl",
            "--file",
            str(output_path),
        ],
        env=connection.env,
    )

    # Fast archive sanity check before the artifact leaves the box.
    _run(["pg_restore", "--list", str(output_path)])


def _upload_file(config: BackupConfig, source: Path, key: str, metadata: dict[str, str]) -> None:
    _require_command("aws")
    if not config.bucket:
        raise RuntimeError("BACKUP_S3_BUCKET is required for S3 uploads")

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
    if not config.bucket:
        raise RuntimeError("BACKUP_S3_BUCKET is required for S3 object checks")
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
    if not config.bucket:
        raise RuntimeError("BACKUP_S3_BUCKET is required for S3 retention")
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
    if not config.bucket:
        raise RuntimeError("BACKUP_S3_BUCKET is required for S3 retention")
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


def _prune_old_local_backups(backup_dir: Path, retention_count: int) -> list[str]:
    dumps = sorted(
        backup_dir.glob("*.dump"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    deleted: list[str] = []
    for dump_path in dumps[retention_count:]:
        manifest_path = dump_path.with_name(f"{dump_path.name}.manifest.json")
        dump_path.unlink(missing_ok=True)
        deleted.append(str(dump_path))
        manifest_path.unlink(missing_ok=True)
        deleted.append(str(manifest_path))

    return deleted


def _store_local_backup(
    config: BackupConfig,
    dump_path: Path,
    manifest_path: Path,
    filename: str,
) -> dict[str, object]:
    if config.local_dir is None:
        raise RuntimeError("BACKUP_LOCAL_DIR is required for local backups")

    backup_dir = config.local_dir / config.destination / "postgres"
    backup_dir.mkdir(parents=True, exist_ok=True)
    final_dump_path = backup_dir / filename
    final_manifest_path = backup_dir / f"{filename}.manifest.json"

    if final_dump_path.exists() or final_manifest_path.exists():
        raise RuntimeError(f"Backup already exists: {final_dump_path}")

    print(f"Storing dump at {final_dump_path}", flush=True)
    shutil.move(str(dump_path), str(final_dump_path))
    shutil.move(str(manifest_path), str(final_manifest_path))

    deleted = _prune_old_local_backups(backup_dir, config.retention_count)
    print(
        f"PostgreSQL backup complete: {final_dump_path} (retention deleted {len(deleted)} file(s))",
        flush=True,
    )

    return {
        "backup_path": str(final_dump_path),
        "manifest_path": str(final_manifest_path),
        "deleted": deleted,
    }


def _store_s3_backup(
    config: BackupConfig,
    dump_path: Path,
    manifest_path: Path,
    backup_key: str,
    manifest_key: str,
    size_bytes: int,
    sha256: str,
) -> dict[str, object]:
    if not config.bucket:
        raise RuntimeError("BACKUP_S3_BUCKET is required for S3 backups")

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

    backup_prefix = str(Path(backup_key).parent).replace("\\", "/")
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


def create_backup(config: BackupConfig) -> dict[str, object]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{DEFAULT_DATABASE_NAME}_{config.destination}_{timestamp}.dump"
    backup_prefix = _s3_key(config.prefix, config.destination, "postgres")
    backup_key = _s3_key(backup_prefix, filename)
    manifest_key = f"{backup_key}.manifest.json"

    config.work_dir.mkdir(parents=True, exist_ok=True)
    with (
        _backup_lock(config),
        TemporaryDirectory(prefix="postgres-", dir=str(config.work_dir)) as tmpdir,
    ):
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
            "filename": filename,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "format": "pg_dump custom",
            "retention_count": config.retention_count,
            "target": config.target,
        }
        if config.target == "s3":
            manifest["s3_bucket"] = config.bucket
            manifest["s3_key"] = backup_key
        else:
            manifest["local_dir"] = str(config.local_dir)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        if config.target == "local":
            return _store_local_backup(config, dump_path, manifest_path, filename)

        return _store_s3_backup(
            config,
            dump_path,
            manifest_path,
            backup_key,
            manifest_key,
            size_bytes,
            sha256,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up PostgreSQL/ParadeDB")
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
    except BackupAlreadyRunning as exc:
        print(f"Skipping PostgreSQL backup: {exc}", flush=True)
        return 0
    except Exception as exc:
        print(f"PostgreSQL backup failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
