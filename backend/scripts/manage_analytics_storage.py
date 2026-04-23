#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add the project root directory to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from db.migrations.analytics_storage import (  # noqa: E402
    analytics_size_report,
    ensure_analytics_storage_schema,
    run_analytics_maintenance,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _pretty_bytes(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def _print_size_report() -> None:
    rows = analytics_size_report()
    if not rows:
        print("No analytics relations found.")
        return

    header = (
        f"{'relation':<48} {'kind':<5} {'rows':>10} {'table':>12} {'indexes':>12} {'total':>12}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['relation_name']:<48} "
            f"{row['relation_kind']:<5} "
            f"{int(row['estimated_rows'] or 0):>10} "
            f"{_pretty_bytes(int(row['table_bytes'] or 0)):>12} "
            f"{_pretty_bytes(int(row['index_bytes'] or 0)):>12} "
            f"{_pretty_bytes(int(row['total_bytes'] or 0)):>12}"
        )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Manage analytics table storage.")
    parser.add_argument(
        "--mode",
        choices=("ensure", "maintenance", "size-report"),
        default="maintenance",
        help="Action to run",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text where applicable",
    )
    args = parser.parse_args()

    if args.mode == "ensure":
        summary = ensure_analytics_storage_schema()
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(f"Ensured analytics storage schema: {summary}")
        return

    if args.mode == "maintenance":
        summary = run_analytics_maintenance()
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(f"Analytics maintenance summary: {summary}")
        return

    if args.json:
        print(json.dumps(analytics_size_report(), indent=2, sort_keys=True))
    else:
        _print_size_report()


if __name__ == "__main__":
    main()
