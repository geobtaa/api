"""Prepare explicitly selected catalog records or a local audit manifest."""

import argparse
import json
from pathlib import Path

from app.services.preview_assets.models import enabled, publication_allowed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*")
    parser.add_argument(
        "--records", type=Path, help="JSON array of records for a reproducible local audit"
    )
    parser.add_argument("--output", type=Path, default=Path("data/preview-audit"))
    parser.add_argument("--recipe", type=Path, help="Explicit rendering recipe JSON")
    parser.add_argument("--layer")
    parser.add_argument(
        "--child-records",
        type=Path,
        help="Local JSON array of child record snapshots for index audits",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run catalog jobs synchronously in isolated child processes",
    )
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text()) if args.recipe else None
    if args.records:
        import sys
        from tempfile import TemporaryDirectory

        from app.services.preview_assets.io import Budget
        from app.services.preview_assets.models import Limits, Manifest, Outcome
        from app.services.preview_assets.process import run_tool

        args.output.mkdir(parents=True, exist_ok=True)
        records = json.loads(args.records.read_text())
        children = json.loads(args.child_records.read_text()) if args.child_records else []
        audit_records = {
            item.get("record", item)["id"]: item.get("record", item)
            for item in [*records, *children]
        }
        report = []
        for entry in records:
            record = entry.get("record", entry)
            with TemporaryDirectory(prefix="preview-audit-job-") as name:
                work = Path(name)
                payload = {
                    "record": record,
                    "recipe": entry.get("recipe", recipe),
                    "selected_layer": entry.get("layer", args.layer),
                    "audit_root": str((args.output / "assets").resolve()),
                    "audit_records": audit_records,
                }
                (work / "input.json").write_text(json.dumps(payload))
                try:
                    run_tool(
                        [
                            sys.executable,
                            "-m",
                            "app.services.preview_assets.job",
                            str(work / "input.json"),
                            str(work / "result.json"),
                        ],
                        Budget(Limits.from_env(), work),
                    )
                    result = Manifest.model_validate_json((work / "result.json").read_text())
                except Exception as exc:
                    result = Manifest(
                        status=getattr(exc, "status", Outcome.INVALID), detail=str(exc)
                    )
            report.append(
                {
                    "id": record["id"],
                    "title": record.get("dct_title_s", record["id"]),
                    "family": entry.get("family"),
                    "manifest": result.model_dump(mode="json"),
                    "browser_review": "not-run",
                    "visual_review": "not-run",
                }
            )
            (args.output / "report.json").write_text(json.dumps(report, indent=2))
            print(record["id"], result.status.value, flush=True)
        return 0
    if not enabled():
        parser.error("Set PREVIEW_ASSETS_ENABLED=true to prepare catalog assets")
    from app.tasks.preview_assets import prepare_resource_preview

    for identifier in args.ids:
        if not publication_allowed(identifier):
            print(identifier, "needs-review: resource is not approved for preview publication")
            continue
        if args.sync:
            result = prepare_resource_preview(identifier, recipe=recipe, selected_layer=args.layer)
            print(identifier, result["status"])
        else:
            from sqlalchemy import select

            from app.services.preview_assets.models import Manifest, Outcome
            from app.services.preview_assets.repository import (
                hydrate_sources,
                record_signature,
                save_attempt,
            )
            from db.models import resources
            from db.session import sync_engine

            with sync_engine.begin() as connection:
                row = (
                    connection.execute(select(resources).where(resources.c.id == identifier))
                    .mappings()
                    .first()
                )
                if row is None:
                    print(identifier, "unavailable")
                    continue
                record = hydrate_sources(connection, row)
                save_attempt(
                    connection,
                    identifier,
                    record_signature(record),
                    Manifest(status=Outcome.QUEUED),
                )
            job = prepare_resource_preview.delay(
                identifier, recipe=recipe, selected_layer=args.layer
            )
            print(identifier, job.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
