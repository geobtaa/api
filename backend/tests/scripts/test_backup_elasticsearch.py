from __future__ import annotations

from scripts import backup_elasticsearch as backup


def test_repository_body_builds_s3_settings(monkeypatch):
    monkeypatch.setattr(backup, "REPOSITORY_TYPE", "s3")
    monkeypatch.setattr(backup, "BACKUP_S3_PREFIX", "btaa-geospatial-api")
    monkeypatch.setenv("BACKUP_S3_BUCKET", "geoportal-dr")
    monkeypatch.setenv("KAMAL_DEST", "prd")
    monkeypatch.setenv("ELASTICSEARCH_SNAPSHOT_S3_STORAGE_CLASS", "STANDARD_IA")
    monkeypatch.setenv("ELASTICSEARCH_SNAPSHOT_S3_SERVER_SIDE_ENCRYPTION", "true")

    body = backup.repository_body()

    assert body == {
        "type": "s3",
        "settings": {
            "bucket": "geoportal-dr",
            "base_path": "btaa-geospatial-api/prd/elasticsearch",
            "client": "default",
            "compress": True,
            "storage_class": "STANDARD_IA",
            "server_side_encryption": True,
        },
    }


def test_repository_body_builds_fs_settings(monkeypatch):
    monkeypatch.setattr(backup, "REPOSITORY_TYPE", "fs")
    monkeypatch.setattr(backup, "REPOSITORY_PATH", "/usr/share/elasticsearch/backups")

    assert backup.repository_body() == {
        "type": "fs",
        "settings": {
            "location": "/usr/share/elasticsearch/backups",
            "compress": True,
        },
    }


def test_scheduled_skip_reason_requires_enabled(monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "false")
    monkeypatch.setenv("KAMAL_DEST", "prd")

    assert backup.scheduled_skip_reason() == "BACKUP_ENABLED is not true"


def test_managed_snapshot_uses_metadata_or_name():
    assert backup.managed_snapshot({"snapshot": "other", "metadata": {"index": backup.INDEX_NAME}})
    assert backup.managed_snapshot({"snapshot": f"{backup.INDEX_NAME}_snapshot_20260520_053000"})
    assert not backup.managed_snapshot({"snapshot": "unrelated_snapshot"})
