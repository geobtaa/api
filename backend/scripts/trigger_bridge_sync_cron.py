from __future__ import annotations

import asyncio
import json
import os

from app.tasks.bridge_sync import _bridge_sync_all_async, bridge_sync_all


async def _run_inline(**kwargs) -> dict:
    # This runner owns a fresh process and loop, including its database pool.
    from db.database import database

    try:
        return await asyncio.wait_for(
            _bridge_sync_all_async(resource_id=None, **kwargs), timeout=60 * 60
        )
    finally:
        if database.is_connected:
            await database.disconnect()


def main() -> None:
    bridge_trigger = os.getenv("BRIDGE_TRIGGER", "incremental_cron")
    changed_since = (os.getenv("CHANGED_SINCE") or "").strip() or None
    resume_from_last_success = changed_since is None
    limit_raw = os.getenv("BRIDGE_LIMIT", "").strip()
    limit = int(limit_raw) if limit_raw else None

    kwargs = {
        "trigger": bridge_trigger,
        "limit": limit,
        "changed_since": changed_since,
        "resume_from_last_success": resume_from_last_success,
    }
    if os.getenv("RUN_NOW", "").strip().lower() in {"1", "true", "yes", "on"}:
        result = asyncio.run(_run_inline(**kwargs))
        print(json.dumps({"queued": "inline", "result": result}, default=str))
        return

    # Avoid public self-HTTP calls from Kamal containers; enqueue the worker task directly.
    # Cron does not need a Celery result subscription just to queue fire-and-forget work.
    task = bridge_sync_all.apply_async(
        kwargs=kwargs,
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
