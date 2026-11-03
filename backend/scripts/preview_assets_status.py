"""Read-only summary of preview attempts, formats, providers, sizes, and asset age."""

import argparse
import json
from pathlib import Path

from app.services.preview_assets.metrics import summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Local audit report instead of the database")
    parser.add_argument("--stale-days", type=int, default=30)
    args = parser.parse_args()
    if args.stale_days < 1:
        parser.error("--stale-days must be positive")
    if args.report:
        records = json.loads(args.report.read_text())
    else:
        from sqlalchemy import select

        from db.models import resource_preview_assets
        from db.session import sync_engine

        with sync_engine.connect() as connection:
            records = list(connection.execute(select(resource_preview_assets)).mappings())
    print(json.dumps(summarize(records, args.stale_days), indent=2))


if __name__ == "__main__":
    main()
