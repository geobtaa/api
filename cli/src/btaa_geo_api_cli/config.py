from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

DEFAULT_BASE_URL = "https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1"
APP_NAME = "btaa-geo-api-cli"


@dataclass
class CliConfig:
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = None
    output: str = "table"
    analytics_enabled: bool = True
    client_instance: str = ""
    profile: str = "default"
    config_path: Path | None = None


def default_config_dir() -> Path:
    override = os.getenv("BTAA_GEO_API_CONFIG_DIR")
    if override:
        return Path(override)
    return Path(user_config_dir(APP_NAME))


def default_config_path() -> Path:
    return default_config_dir() / "config.json"


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_config(
    *,
    profile: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    output: str | None = None,
    analytics: bool | None = None,
    config_path: Path | None = None,
) -> CliConfig:
    path = config_path or default_config_path()
    raw = _read_config(path)
    selected_profile = profile or os.getenv("BTAA_GEO_API_PROFILE") or raw.get("current_profile")
    selected_profile = selected_profile or "default"
    profiles = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else {}
    profile_data = profiles.get(selected_profile, {}) if isinstance(profiles, dict) else {}

    env_analytics = os.getenv("BTAA_GEO_API_ANALYTICS")
    if analytics is None and env_analytics is not None:
        analytics = env_analytics.lower() not in {"0", "false", "no", "off"}

    instance = raw.get("client_instance")
    if not isinstance(instance, str) or not instance:
        instance = str(uuid.uuid4())
        raw["client_instance"] = instance
        _write_config(path, raw)

    return CliConfig(
        base_url=(
            base_url
            or os.getenv("BTAA_API_BASE_URL")
            or os.getenv("BTAA_GEO_API_BASE_URL")
            or profile_data.get("base_url")
            or DEFAULT_BASE_URL
        ).rstrip("/"),
        api_key=api_key
        or os.getenv("BTAA_API_KEY")
        or os.getenv("BTAA_GEO_API_KEY")
        or profile_data.get("api_key"),
        output=output or os.getenv("BTAA_GEO_API_OUTPUT") or profile_data.get("output") or "table",
        analytics_enabled=(
            analytics
            if analytics is not None
            else bool(profile_data.get("analytics_enabled", raw.get("analytics_enabled", True)))
        ),
        client_instance=instance,
        profile=selected_profile,
        config_path=path,
    )


def set_config_value(
    key: str, value: str, *, profile: str = "default", config_path: Path | None = None
) -> Path:
    path = config_path or default_config_path()
    raw = _read_config(path)
    if key == "profile":
        raw["current_profile"] = value
    elif key == "analytics.enabled":
        raw["analytics_enabled"] = value.lower() not in {"0", "false", "no", "off"}
    else:
        profiles = raw.setdefault("profiles", {})
        profile_data = profiles.setdefault(profile, {})
        profile_data[key] = value
    _write_config(path, raw)
    return path
