import os

from appsignal import Appsignal


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _env_int_first(*names: str, default: str) -> int:
    value = _env_first(*names, default=default)
    return int(value)


appsignal = Appsignal(
    name=_env_first(
        "APPSIGNAL_BACKEND_APP_NAME",
        "APPSIGNAL_APP_NAME",
        default="BTAA Geospatial API",
    ),
    active=_env_flag(
        "APPSIGNAL_BACKEND_ACTIVE",
        os.getenv("APPSIGNAL_ACTIVE", "true"),
    ),
    environment=_env_first("APPSIGNAL_BACKEND_APP_ENV", "APPSIGNAL_APP_ENV"),
    revision=os.getenv("APP_REVISION"),
    enable_host_metrics=_env_flag(
        "APPSIGNAL_BACKEND_ENABLE_HOST_METRICS",
        os.getenv("APPSIGNAL_ENABLE_HOST_METRICS", "true"),
    ),
    host_role=_env_first(
        "APPSIGNAL_BACKEND_HOST_ROLE",
        "APPSIGNAL_HOST_ROLE",
        default="backend",
    ),
    working_directory_path=_env_first(
        "APPSIGNAL_BACKEND_WORKING_DIRECTORY_PATH",
        "APPSIGNAL_WORKING_DIRECTORY_PATH",
        default="/tmp/appsignal-backend",
    ),
    opentelemetry_port=_env_int_first(
        "APPSIGNAL_BACKEND_OPENTELEMETRY_PORT",
        "APPSIGNAL_OPENTELEMETRY_PORT",
        default="8099",
    ),
)
