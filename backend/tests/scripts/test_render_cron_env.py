from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.render_cron_env import DEFAULT_OUTPUT_PATH, render_cron_env_exports, write_cron_env


def test_render_cron_env_exports_filters_and_quotes_values():
    rendered = render_cron_env_exports(
        {
            "DATABASE_URL": "postgresql://user:p@ss word@db.example/btaa",
            "REDIS_HOST": "redis.internal",
            "GEOPORTAL_BASE_URL": "https://geo.btaa.org",
            "BRIDGE_SYNC_LOCAL_TIMEZONE": "America/Chicago",
            "BACKUP_ENABLED": "true",
            "AWS_ACCESS_KEY_ID": "example-key",
            "UNRELATED_KEY": "ignore-me",
        }
    )

    assert "export DATABASE_URL='postgresql://user:p@ss word@db.example/btaa'" in rendered
    assert "export REDIS_HOST=redis.internal" in rendered
    assert "export GEOPORTAL_BASE_URL=https://geo.btaa.org" in rendered
    assert "export BRIDGE_SYNC_LOCAL_TIMEZONE=America/Chicago" in rendered
    assert "export BACKUP_ENABLED=true" in rendered
    assert "export AWS_ACCESS_KEY_ID=example-key" in rendered
    assert "UNRELATED_KEY" not in rendered


def test_write_cron_env_writes_private_bootstrap_file(tmp_path):
    output_path = tmp_path / "cron.env"

    written_path = write_cron_env(
        str(output_path),
        {
            "DATABASE_URL": "postgresql://example",
            "PYTHONPATH": "/app",
        },
    )

    assert written_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")
    assert os.stat(output_path).st_mode & 0o777 == 0o600


def test_default_output_path_is_tmp_bootstrap_file():
    assert DEFAULT_OUTPUT_PATH == "/tmp/cron-container-env.sh"


def test_clean_cron_shell_restores_bridge_auth_and_pool_limits(tmp_path):
    expected = {
        "BTAA_GEOSPATIAL_API_KEY": "test-key-with spaces",
        "BTAA_GEOSPATIAL_API_KEYS": "key-one,key-two",
        "DB_POOL_MIN": "1",
        "DB_POOL_MAX": "2",
        "SQLALCHEMY_ASYNC_POOL_SIZE": "1",
        "SQLALCHEMY_ASYNC_MAX_OVERFLOW": "0",
    }
    snapshot = write_cron_env(str(tmp_path / "cron.env"), expected)
    bootstrap = Path(__file__).resolve().parents[2] / "scripts" / "cron_env.sh"
    command = "\n".join(f'printf "%s\\n" "${key}"' for key in expected)
    result = subprocess.run(
        ["/bin/bash", "-c", command],
        env={"BASH_ENV": str(bootstrap), "CRON_ENV_OUTPUT_PATH": str(snapshot)},
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.splitlines() == list(expected.values())
