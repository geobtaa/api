from __future__ import annotations

import json
import os

from app.tasks.bridge_sync import bridge_sync_all


def main() -> None:
    bridge_trigger = os.getenv("BRIDGE_TRIGGER", "incremental_cron")
    changed_since = (os.getenv("CHANGED_SINCE") or "").strip() or None
    resume_from_last_success = changed_since is None
    limit_raw = os.getenv("BRIDGE_LIMIT", "").strip()
    limit = int(limit_raw) if limit_raw else None

    # Avoid public self-HTTP calls from Kamal containers; enqueue the worker task directly.
    # Cron does not need a Celery result subscription just to queue fire-and-forget work.
    task = bridge_sync_all.apply_async(
        kwargs={
            "trigger": bridge_trigger,
            "limit": limit,
            "changed_since": changed_since,
            "resume_from_last_success": resume_from_last_success,
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
                "resume_from_last_success": resume_from_last_success,
            }
        )
    )


if __name__ == "__main__":
    main()
