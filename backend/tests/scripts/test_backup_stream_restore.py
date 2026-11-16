"""Opt-in full PostgreSQL archive round trip against a disposable database server."""

import hashlib
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg2
import pytest
from psycopg2 import sql

from scripts import backup_postgres_to_s3 as backup
from tests.scripts.test_backup_postgres_to_s3 import MultipartSink


def test_streamed_archive_restores_schema_and_binary_data(monkeypatch, tmp_path: Path):
    url = os.getenv("BACKUP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires a disposable PostgreSQL server and matching pg_dump/pg_restore")
    source, target = "dump_source_" + uuid4().hex, "dump_target_" + uuid4().hex
    admin = psycopg2.connect(url)
    admin.autocommit = True
    parts = urlsplit(url)

    def database_url(name):
        return urlunsplit(parts._replace(path="/" + name))

    def command_connection(name):
        # Docker test-client wrappers can reach the same disposable server on
        # its container port, while psycopg uses the mapped workstation port.
        client_url = database_url(name)
        if override := os.getenv("BACKUP_TEST_CLIENT_PORT"):
            client_url = client_url.replace(f":{parts.port}/", f":{override}/")
        return client_url

    try:
        with admin.cursor() as cur:
            for name in (source, target):
                cur.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name))
                )
        payload = bytes(range(256)) * 16384
        with psycopg2.connect(database_url(source)) as conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE sample(id integer PRIMARY KEY, label text NOT NULL, body bytea)"
            )
            cur.execute("INSERT INTO sample VALUES (%s,%s,%s)", (1, "full archive", payload))
            cur.execute("CREATE INDEX sample_label_idx ON sample(label)")
        # Real pg_dump output flows through real subprocess pipes. A local sink
        # stands in for S3; cloud permissions are tested separately.
        saved = tmp_path / "stream.dump"
        sink = MultipartSink(saved)
        monkeypatch.setattr(backup, "_multipart_client", lambda: sink)
        config = backup.BackupConfig(
            destination="test",
            target="s3",
            prefix="test",
            retention_count=1,
            database_url=command_connection(source),
            bucket="local-sink",
            work_dir=tmp_path,
            stream=True,
        )
        size, digest = backup._stream_pg_dump(config, "test.dump")
        assert size == saved.stat().st_size
        assert digest == hashlib.sha256(saved.read_bytes()).hexdigest()
        target_config = replace(config, database_url=command_connection(target))
        connection = backup._pg_connection_args(target_config.database_url)
        subprocess.run(
            [shutil.which("pg_restore"), *connection.args, "--exit-on-error", "--no-owner"],
            input=saved.read_bytes(),
            env=connection.env,
            check=True,
            capture_output=True,
        )
        with psycopg2.connect(database_url(target)) as conn, conn.cursor() as cur:
            cur.execute("SELECT id,label,body FROM sample")
            row = cur.fetchone()
            assert row[:2] == (1, "full archive")
            assert bytes(row[2]) == payload
            cur.execute("SELECT indexname FROM pg_indexes WHERE tablename='sample'")
            assert {r[0] for r in cur.fetchall()} == {"sample_pkey", "sample_label_idx"}
    finally:
        with admin.cursor() as cur:
            for name in (source, target):
                cur.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
                )
        admin.close()
