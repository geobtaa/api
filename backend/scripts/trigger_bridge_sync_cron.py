from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests


def _previous_utc_day_start_iso_z() -> str:
    """
    Return ISO-8601 UTC datetime for the previous *local* day at 00:00:00,
    converted to UTC (so it works with the bridge API's ISO-8601 parsing).
    """
    now_local = datetime.now().astimezone()
    prev_day = (now_local - timedelta(days=1)).date()

    dt_local_midnight = datetime(
        prev_day.year,
        prev_day.month,
        prev_day.day,
        0,
        0,
        0,
        tzinfo=now_local.tzinfo,
    )
    dt_utc = dt_local_midnight.astimezone(timezone.utc)
    return dt_utc.isoformat().replace("+00:00", "Z")


def main() -> None:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "changeme")
    application_url = os.getenv("APPLICATION_URL", "").rstrip("/")
    bridge_trigger = os.getenv("BRIDGE_TRIGGER", "manual")

    if not application_url:
        raise RuntimeError("APPLICATION_URL is required")

    changed_since = os.getenv("CHANGED_SINCE") or _previous_utc_day_start_iso_z()

    url = f"{application_url}/api/v1/admin/bridge/sync"
    payload: dict[str, object] = {"bridge_trigger": bridge_trigger, "changed_since": changed_since}

    # Basic Auth via (user, pass) tuple (FastAPI/HTTPBasic).
    resp = requests.post(url, json=payload, auth=(admin_username, admin_password), timeout=60)
    resp.raise_for_status()

    # Cron logs should be readable from `docker logs`; print response body.
    print(resp.text)


if __name__ == "__main__":
    main()
