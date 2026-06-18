from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts import backup_postgres_to_s3 as backup


def test_normalize_database_url_strips_async_driver():
    assert (
        backup._normalize_database_url(
            "postgresql+asyncpg://postgres:secret@paradedb:5432/btaa_geospatial_api"
        )
        == "postgresql://postgres:secret@paradedb:5432/btaa_geospatial_api"
    )


def test_s3_key_joins_and_strips_slashes():
    assert (
        backup._s3_key("/btaa-geospatial-api/", "prd", "/postgres/", "dump.dump")
        == "btaa-geospatial-api/prd/postgres/dump.dump"
    )


def test_pg_connection_args_keep_password_out_of_args(monkeypatch):
    monkeypatch.setenv("EXISTING_ENV", "kept")

    connection = backup._pg_connection_args(
        "postgresql://postgres:p%40ss@paradedb:5432/btaa_geospatial_api"
    )

    assert connection.args == [
        "--host",
        "paradedb",
        "--dbname",
        "btaa_geospatial_api",
        "--port",
        "5432",
        "--username",
        "postgres",
    ]
    assert "p@ss" not in " ".join(connection.args)
    assert connection.env["PGPASSWORD"] == "p@ss"
    assert connection.env["EXISTING_ENV"] == "kept"


def test_scheduled_backup_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "false")
    monkeypatch.setenv("KAMAL_DEST", "prd")

    assert backup._should_skip_scheduled_backup(force=False) == "BACKUP_ENABLED is not true"


def test_scheduled_backup_skips_non_required_destination(monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "true")
    monkeypatch.setenv("BACKUP_REQUIRED_DEST", "prd")
    monkeypatch.setenv("KAMAL_DEST", "dev2")

    assert (
        backup._should_skip_scheduled_backup(force=False)
        == "KAMAL_DEST=dev2 does not match BACKUP_REQUIRED_DEST=prd"
    )


def test_prune_old_backups_keeps_newest_count(monkeypatch, tmp_path: Path):
    config = backup.BackupConfig(
        destination="prd",
        target="s3",
        bucket="bucket",
        prefix="btaa-geospatial-api",
        retention_count=3,
        database_url="postgresql://postgres:secret@db/example",
        work_dir=tmp_path,
    )
    objects = [
        {"Key": "prefix/backup-1.dump", "LastModified": "2026-05-20T05:30:01Z"},
        {"Key": "prefix/backup-2.dump", "LastModified": "2026-05-20T05:30:02Z"},
        {"Key": "prefix/backup-3.dump", "LastModified": "2026-05-20T05:30:03Z"},
        {"Key": "prefix/backup-4.dump", "LastModified": "2026-05-20T05:30:04Z"},
        {"Key": "prefix/backup-4.dump.manifest.json", "LastModified": "2026-05-20T05:30:04Z"},
    ]
    deleted: list[str] = []

    monkeypatch.setattr(backup, "_list_objects", lambda _config, _prefix: objects)
    monkeypatch.setattr(backup, "_delete_object", lambda _config, key: deleted.append(key))

    assert backup._prune_old_backups(config, "prefix/") == [
        "prefix/backup-1.dump",
        "prefix/backup-1.dump.manifest.json",
    ]
    assert deleted == [
        "prefix/backup-1.dump",
        "prefix/backup-1.dump.manifest.json",
    ]


def test_build_config_supports_local_target(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:secret@db/example")
    monkeypatch.setenv("KAMAL_DEST", "prd")
    monkeypatch.setenv("BACKUP_POSTGRES_TARGET", "local")
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path / "backups"))
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)

    config = backup._build_config()

    assert config.target == "local"
    assert config.bucket is None
    assert config.local_dir == tmp_path / "backups"
    assert config.work_dir == tmp_path / "backups" / ".tmp"


def test_prune_old_local_backups_keeps_newest_count(tmp_path: Path):
    backup_dir = tmp_path / "postgres"
    backup_dir.mkdir()
    for index in range(4):
        dump = backup_dir / f"backup-{index}.dump"
        manifest = backup_dir / f"backup-{index}.dump.manifest.json"
        dump.write_text("dump", encoding="utf-8")
        manifest.write_text("{}", encoding="utf-8")
        timestamp = 1_800_000_000 + index
        dump.touch()
        manifest.touch()

        os.utime(dump, (timestamp, timestamp))
        os.utime(manifest, (timestamp, timestamp))

    deleted = backup._prune_old_local_backups(backup_dir, 2)

    assert sorted(path.name for path in backup_dir.iterdir()) == [
        "backup-2.dump",
        "backup-2.dump.manifest.json",
        "backup-3.dump",
        "backup-3.dump.manifest.json",
    ]
    assert len(deleted) == 4


def test_create_backup_local_stores_dump_and_manifest(monkeypatch, tmp_path: Path):
    def fake_create_pg_dump(_config, output_path: Path):
        output_path.write_text("compressed dump", encoding="utf-8")

    monkeypatch.setattr(backup, "_create_pg_dump", fake_create_pg_dump)

    config = backup.BackupConfig(
        destination="prd",
        target="local",
        prefix="btaa-geospatial-api",
        retention_count=3,
        database_url="postgresql://postgres:secret@db/example",
        work_dir=tmp_path / ".tmp",
        local_dir=tmp_path / "backups",
    )

    result = backup.create_backup(config)

    backup_path = Path(str(result["backup_path"]))
    manifest_path = Path(str(result["manifest_path"]))
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "compressed dump"
    assert manifest_path.exists()
    assert '"target": "local"' in manifest_path.read_text(encoding="utf-8")


def test_create_backup_skips_when_backup_lock_is_held(monkeypatch, tmp_path: Path):
    called = False

    def fake_create_pg_dump(_config, _output_path: Path):
        nonlocal called
        called = True

    monkeypatch.setattr(backup, "_create_pg_dump", fake_create_pg_dump)

    config = backup.BackupConfig(
        destination="prd",
        target="local",
        prefix="btaa-geospatial-api",
        retention_count=3,
        database_url="postgresql://postgres:secret@db/example",
        work_dir=tmp_path / ".tmp",
        local_dir=tmp_path / "backups",
    )
    config.work_dir.mkdir(parents=True)
    lock_path = config.work_dir / backup.LOCK_FILENAME
    lock_path.write_text(json.dumps({"pid": os.getpid()}) + "\n", encoding="utf-8")

    with pytest.raises(backup.BackupAlreadyRunning, match="already running"):
        backup.create_backup(config)

    assert called is False


def test_backup_lock_replaces_stale_lock(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(backup, "_pid_is_running", lambda _pid: False)

    config = backup.BackupConfig(
        destination="prd",
        target="local",
        prefix="btaa-geospatial-api",
        retention_count=3,
        database_url="postgresql://postgres:secret@db/example",
        work_dir=tmp_path / ".tmp",
        local_dir=tmp_path / "backups",
    )
    config.work_dir.mkdir(parents=True)
    lock_path = config.work_dir / backup.LOCK_FILENAME
    lock_path.write_text(json.dumps({"pid": 123}) + "\n", encoding="utf-8")

    with backup._backup_lock(config):
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["pid"] == os.getpid()
        assert payload["destination"] == "prd"

    assert not lock_path.exists()


def test_main_skips_when_backup_already_running(monkeypatch, capsys):
    monkeypatch.setattr(backup.sys, "argv", ["backup_postgres_to_s3.py"])
    monkeypatch.setattr(backup, "_should_skip_scheduled_backup", lambda force: None)
    monkeypatch.setattr(backup, "_build_config", object)

    def fake_create_backup(_config):
        raise backup.BackupAlreadyRunning("PostgreSQL backup already running (pid=123)")

    monkeypatch.setattr(backup, "create_backup", fake_create_backup)

    assert backup.main() == 0
    assert (
        capsys.readouterr().out
        == "Skipping PostgreSQL backup: PostgreSQL backup already running (pid=123)\n"
    )
