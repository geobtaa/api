from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tasks.bridge_sync import bridge_sync_all

DEFAULT_BRIDGE_SYNC_LOCAL_TIMEZONE = "America/Chicago"


def _bridge_sync_local_timezone() -> ZoneInfo:
    tz_name = (
        os.getenv("BRIDGE_SYNC_LOCAL_TIMEZONE")
        or os.getenv("TZ")
        or DEFAULT_BRIDGE_SYNC_LOCAL_TIMEZONE
    ).strip()
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_BRIDGE_SYNC_LOCAL_TIMEZONE)


def _previous_utc_day_start_iso_z(now: datetime | None = None) -> str:
    """
    Return ISO-8601 UTC datetime for the previous America/Chicago-local day at
    00:00:00, converted to UTC for the bridge API.
    """
    local_tz = _bridge_sync_local_timezone()
    now_local = now.astimezone(local_tz) if now else datetime.now(local_tz)
    prev_day = (now_local - timedelta(days=1)).date()

    dt_local_midnight = datetime(
        prev_day.year,
        prev_day.month,
        prev_day.day,
        0,
        0,
        0,
        tzinfo=local_tz,
    )
    dt_utc = dt_local_midnight.astimezone(timezone.utc)
    return dt_utc.isoformat().replace("+00:00", "Z")


def main() -> None:
    bridge_trigger = os.getenv("BRIDGE_TRIGGER", "nightly_cron")
    changed_since = os.getenv("CHANGED_SINCE") or _previous_utc_day_start_iso_z()
    limit_raw = os.getenv("BRIDGE_LIMIT", "").strip()
    limit = int(limit_raw) if limit_raw else None

    # Avoid public self-HTTP calls from Kamal containers; enqueue the worker task directly.
    # Cron does not need a Celery result subscription just to queue fire-and-forget work.
    task = bridge_sync_all.apply_async(
        kwargs={
            "trigger": bridge_trigger,
            "limit": limit,
            "changed_since": changed_since,
        },
        ignore_result=True,
    )
    print(
        json.dumps(
            {
                "queued": "kithe_bridge",
                "task_id": task.id,
                "bridge_trigger": bridge_trigger,
                "limit": limit,
                "changed_since": changed_since,
            }
        )
    )


if __name__ == "__main__":
    main()
