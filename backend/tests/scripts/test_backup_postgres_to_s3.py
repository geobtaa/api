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
    monkeypatch.delenv("BACKUP_RETENTION_COUNT", raising=False)

    config = backup._build_config()

    assert config.target == "local"
    assert config.bucket is None
    assert config.local_dir == tmp_path / "backups"
    assert config.work_dir == tmp_path / "backups" / ".tmp"
    assert config.retention_count == 1


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


def streaming_config(tmp_path):
    return backup.BackupConfig(
        destination="test",
        target="s3",
        prefix="tests",
        retention_count=2,
        database_url="postgresql://postgres:secret@db/example",
        work_dir=tmp_path,
        bucket="test-bucket",
        stream=True,
    )


def test_capacity_failure_preserves_previous_backup(monkeypatch, tmp_path):
    from dataclasses import replace
    from types import SimpleNamespace

    config = replace(streaming_config(tmp_path), target="local", stream=False, local_dir=tmp_path)
    old = tmp_path / "test/postgres/previous.dump"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"previous complete backup")
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda _: SimpleNamespace(free=10))
    monkeypatch.setattr(
        backup, "_create_pg_dump", lambda *_: pytest.fail("must fail before dumping")
    )
    with pytest.raises(RuntimeError, match="Insufficient backup staging space"):
        backup.create_backup(config)
    assert old.read_bytes() == b"previous complete backup"


def test_streaming_commits_manifest_before_retention(monkeypatch, tmp_path):
    import hashlib

    payload = b"PGDMP-test-data"
    uploaded = {}
    events = []
    config = streaming_config(tmp_path)

    def stream(_config, key):
        uploaded[key] = payload
        return len(payload), hashlib.sha256(payload).hexdigest()

    def upload(_config, path, key, _metadata):
        uploaded[key] = path.read_bytes()
        events.append("manifest")

    def prune(*_):
        events.append("prune")
        return []

    monkeypatch.setattr(backup, "_stream_pg_dump", stream)
    monkeypatch.setattr(backup, "_upload_file", upload)
    monkeypatch.setattr(backup, "_head_object", lambda _, k: {"ContentLength": len(uploaded[k])})
    monkeypatch.setattr(backup, "_prune_old_backups", prune)
    monkeypatch.setattr(backup, "_create_pg_dump", lambda *_: pytest.fail("must not stage dump"))
    result = backup.create_backup(config)
    manifest = json.loads(uploaded[result["manifest_key"]])
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["size_bytes"] == len(payload)
    assert events == ["manifest", "prune"]
    assert not list(tmp_path.rglob("*.dump"))


@pytest.mark.parametrize("failure", ["dump", "size", "manifest"])
def test_streaming_failure_never_prunes_successful_backups(monkeypatch, tmp_path, failure):
    config = streaming_config(tmp_path)
    deleted = []

    def stream(*_):
        if failure == "dump":
            raise RuntimeError("dump failed")
        return 42, "checksum"

    monkeypatch.setattr(backup, "_stream_pg_dump", stream)
    monkeypatch.setattr(
        backup, "_head_object", lambda *_: {"ContentLength": 0 if failure == "size" else 42}
    )
    monkeypatch.setattr(backup, "_upload_file", lambda *_: None)
    monkeypatch.setattr(backup, "_delete_object", lambda _, key: deleted.append(key))
    monkeypatch.setattr(
        backup, "_prune_old_backups", lambda *_: pytest.fail("must preserve backups")
    )
    with pytest.raises(RuntimeError):
        backup.create_backup(config)
    assert len(deleted) == 2
    assert all(key.startswith("tests/test/postgres/") for key in deleted)


class MultipartSink:
    def __init__(self, path, fail_part=False):
        self.path, self.fail_part = path, fail_part
        self.completed, self.aborted = False, False
        self.options = None

    def create_multipart_upload(self, **kwargs):
        self.options = kwargs
        return {"UploadId": "test-upload"}

    def upload_part(self, **kwargs):
        if self.fail_part:
            raise RuntimeError("upload failed")
        with self.path.open("ab") as out:
            out.write(kwargs["Body"])
        return {"ETag": str(kwargs["PartNumber"])}

    def complete_multipart_upload(self, **kwargs):
        self.completed = True

    def abort_multipart_upload(self, **kwargs):
        self.aborted = True

    def close(self):
        pass


@pytest.mark.parametrize("exit_code,fail_part", [(0, False), (1, False), (0, True)])
def test_streaming_subprocess_handles_partial_dump(monkeypatch, tmp_path, exit_code, fail_part):
    """A partial archive or failed part aborts its multipart upload, never commits it."""
    import hashlib
    import sys
    from dataclasses import replace

    dump = tmp_path / "pg_dump"
    dump.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "sys.stdout.buffer.write(b'PGDMP' + b'x'*2000000)\n"
        f"sys.exit({exit_code})\n"
    )
    dump.chmod(0o755)
    saved = tmp_path / "uploaded"
    client = MultipartSink(saved, fail_part)
    monkeypatch.setattr(backup, "_multipart_client", lambda: client)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    config = replace(streaming_config(tmp_path), sse="AES256")
    if exit_code or fail_part:
        with pytest.raises(RuntimeError, match="failed"):
            backup._stream_pg_dump(config, "backup.dump")
        assert client.aborted
        assert not client.completed
    else:
        size, digest = backup._stream_pg_dump(config, "backup.dump")
        assert size == 2000005
        assert digest == hashlib.sha256(saved.read_bytes()).hexdigest()
        assert client.completed
        assert not client.aborted
        assert client.options["ServerSideEncryption"] == "AES256"


def test_backup_lock_cleanup_does_not_hide_dump_failure(tmp_path):
    config = streaming_config(tmp_path)
    with pytest.raises(RuntimeError, match="dump failed"):
        with backup._backup_lock(config):
            (tmp_path / backup.LOCK_FILENAME).unlink()
            raise RuntimeError("dump failed")
