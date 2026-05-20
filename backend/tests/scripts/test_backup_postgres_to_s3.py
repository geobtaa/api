from __future__ import annotations

from pathlib import Path

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
