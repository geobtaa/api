from __future__ import annotations

import asyncio
import json
import os

from app.tasks.gin_blog_sync import gin_blog_sync, run_gin_blog_sync


def _env_truthy(name: str) -> bool:
    value = os.getenv(name, "")
    return value.lower() in {"1", "true", "yes", "on"}


def main() -> None:
    run_now = _env_truthy("RUN_NOW")

    # Avoid public self-HTTP calls from Kamal containers. Enqueue via Celery directly,
    # or run the sync inline when RUN_NOW is requested by the Make target.
    if run_now:
        result = asyncio.run(run_gin_blog_sync())
        print(json.dumps({"queued": "inline", "result": result}, default=str))
        return

    task = gin_blog_sync.apply_async(ignore_result=True)
    print(json.dumps({"queued": "gin_blog_sync", "task_id": task.id}))


if __name__ == "__main__":
    main()
