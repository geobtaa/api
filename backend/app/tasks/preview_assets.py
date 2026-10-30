"""Explicit, isolated background preparation. No conversion on resource reads."""

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from celery import shared_task
from sqlalchemy import select, text

from app.services.preview_assets.io import Budget
from app.services.preview_assets.models import Limits, Manifest, Outcome, enabled
from app.services.preview_assets.process import run_tool
from app.services.preview_assets.repository import hydrate_sources, record_signature, save_attempt
from db.models import resources
from db.session import sync_engine


@shared_task(
    bind=True,
    name="prepare_resource_preview",
    queue="previews",
    soft_time_limit=920,
    time_limit=940,
    max_retries=3,
)
def prepare_resource_preview(self, resource_id, recipe=None, selected_layer=None):
    if not enabled():
        return {"status": "disabled"}
    # PostgreSQL session locks deduplicate resources and enforce a global cap
    # across all worker processes; disconnects release locks automatically.
    with sync_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lease:
        locks = []
        try:
            if not lease.execute(
                text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"),
                {"key": "preview-resource:" + resource_id},
            ).scalar():
                return {"status": "processing"}
            locks.append("preview-resource:" + resource_id)
            for slot in range(max(1, int(os.getenv("PREVIEW_CONCURRENT_CONVERSIONS", "2")))):
                name = f"preview-conversion:{slot}"
                if lease.execute(
                    text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"), {"key": name}
                ).scalar():
                    locks.append(name)
                    break
            else:
                raise self.retry(countdown=30)
            with sync_engine.begin() as connection:
                row = (
                    connection.execute(select(resources).where(resources.c.id == resource_id))
                    .mappings()
                    .first()
                )
                if row is None:
                    return {"status": "unavailable"}
                record = hydrate_sources(connection, row)
                signature = record_signature(record)
                save_attempt(
                    connection, resource_id, signature, Manifest(status=Outcome.PROCESSING)
                )
            try:
                with TemporaryDirectory(prefix="btaa-preview-job-") as name:
                    directory = Path(name)
                    (directory / "input.json").write_text(
                        json.dumps(
                            {"record": record, "recipe": recipe, "selected_layer": selected_layer},
                            default=str,
                        )
                    )
                    budget = Budget(Limits.from_env(), directory)
                    run_tool(
                        [
                            sys.executable,
                            "-m",
                            "app.services.preview_assets.job",
                            str(directory / "input.json"),
                            str(directory / "result.json"),
                        ],
                        budget,
                    )
                    result = Manifest.model_validate_json((directory / "result.json").read_text())
            except Exception as exc:
                result = Manifest(status=getattr(exc, "status", Outcome.INVALID), detail=str(exc))
            with sync_engine.begin() as connection:
                save_attempt(connection, resource_id, signature, result)
            if result.status != Outcome.READY and any(
                "Provider busy; retry later" in attempt.get("detail", "")
                for attempt in result.metrics.get("source_attempts", [])
            ):
                raise self.retry(countdown=30)
            return result.model_dump(mode="json")
        finally:
            for name in reversed(locks):
                lease.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": name}
                )
