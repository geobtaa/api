from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from app.tasks.bridge_sync import bridge_sync_all


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
    bridge_trigger = os.getenv("BRIDGE_TRIGGER", "manual")
    changed_since = os.getenv("CHANGED_SINCE") or _previous_utc_day_start_iso_z()
    limit_raw = os.getenv("BRIDGE_LIMIT", "").strip()
    limit = int(limit_raw) if limit_raw else None

    # Avoid public self-HTTP calls from Kamal containers; enqueue the worker task directly.
    task = bridge_sync_all.delay(
        trigger=bridge_trigger,
        limit=limit,
        changed_since=changed_since,
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
