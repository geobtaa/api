from __future__ import annotations

import os
import shlex
import stat
import sys
from pathlib import Path

DEFAULT_OUTPUT_PATH = "/tmp/cron-container-env.sh"

ALLOWED_EXACT_KEYS = {
    "APPLICATION_URL",
    "BRIDGE_SYNC_LOCAL_TIMEZONE",
    "DATABASE_URL",
    "ENDPOINT_CACHE",
    "IS_DOCKER",
    "KAMAL_DEST",
    "PYTHONPATH",
    "STATIC_MAPS_DIR",
    "TZ",
}

ALLOWED_PREFIXES = (
    "ADMIN_",
    "APP_",
    "BRIDGE_",
    "CACHE_",
    "CELERY_",
    "CORS_",
    "ELASTICSEARCH_",
    "KITHE_BRIDGE_",
    "LOG_",
    "OPENAI_",
    "POSTGRES_",
    "RATE_LIMIT_",
    "REDIS_",
    "SEARCH_ENGINE_",
    "SENDMAIL_",
    "SMTP_",
    "THUMBNAIL_",
    "WEB_",
)


def _should_export(key: str) -> bool:
    return key in ALLOWED_EXACT_KEYS or key.startswith(ALLOWED_PREFIXES)


def render_cron_env_exports(env: dict[str, str] | None = None) -> str:
    source = env or dict(os.environ)
    lines = ["#!/usr/bin/env bash", ""]

    for key in sorted(source):
        if _should_export(key):
            lines.append(f"export {key}={shlex.quote(source[key])}")

    return "\n".join(lines) + "\n"


def write_cron_env(output_path: str, env: dict[str, str] | None = None) -> Path:
    output = Path(output_path)
    output.write_text(render_cron_env_exports(env), encoding="utf-8")
    output.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return output


def main() -> None:
    output_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.getenv("CRON_ENV_OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
    )
    write_cron_env(output_path)


if __name__ == "__main__":
    main()
