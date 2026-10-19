from __future__ import annotations

import os
import shlex
import subprocess
import sys
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
        "APPSIGNAL_BACKEND_ACTIVE": "false",
        "APPSIGNAL_BACKEND_APP_NAME": "Cron regression test",
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


def test_scheduled_bridge_commands_find_appsignal_config_from_clean_shell(tmp_path):
    """Exercise both installed commands from cron's unrelated starting directory."""
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "__appsignal__.py").write_text(
        "from appsignal import Appsignal\n"
        "appsignal = Appsignal(name='cron-regression', active=False)\n"
    )
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import os, appsignal\n"
        "assert os.environ['APPSIGNAL_BACKEND_ACTIVE'] == 'false'\n"
        "assert os.environ['RUN_NOW'] == '1'\n"
        "appsignal.start()\n"
        "print(os.environ['BRIDGE_TRIGGER'])\n"
    )
    snapshot = write_cron_env(str(tmp_path / "cron.env"), {"APPSIGNAL_BACKEND_ACTIVE": "false"})
    root = Path(__file__).resolve().parents[3]
    triggers = []
    for line in (root / "config" / "crontab").read_text().splitlines():
        if line.startswith("#") or "trigger_bridge_sync_cron.py" not in line:
            continue
        command = line.split(maxsplit=5)[5].split(" >> ", 1)[0]
        command = command.replace("/app/backend", shlex.quote(str(backend)))
        command = command.replace("/opt/venv/bin/python3", shlex.quote(sys.executable))
        command = command.replace(
            "/app/scripts/trigger_bridge_sync_cron.py", shlex.quote(str(probe))
        )
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=tmp_path,
            env={
                "BASH_ENV": str(root / "backend" / "scripts" / "cron_env.sh"),
                "CRON_ENV_OUTPUT_PATH": str(snapshot),
            },
            check=True,
            capture_output=True,
            text=True,
        )
        triggers.append(result.stdout.strip())
    assert triggers == ["incremental_cron", "nightly_cron"]
