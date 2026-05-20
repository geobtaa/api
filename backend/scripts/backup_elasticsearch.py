#!/usr/bin/env python3
"""
Elasticsearch Backup Script

This script manages Elasticsearch snapshots for backup and disaster recovery:
- Create snapshot repository (filesystem-based)
- Create snapshots with automatic naming
- List existing snapshots
- Restore from snapshots
- Clean up old snapshots based on retention policy

Can be run locally or remotely via Kamal:
  python scripts/backup_elasticsearch.py --create
  python scripts/backup_elasticsearch.py --list
  python scripts/backup_elasticsearch.py --restore snapshot_name
  python scripts/backup_elasticsearch.py --cleanup --keep-days 7
  kamal app exec "python scripts/backup_elasticsearch.py --create"
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import NotFoundError, RequestError

# Load environment variables
load_dotenv()

# Use ELASTICSEARCH_URL from environment or default
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

# Snapshot repository configuration. The historical default is a filesystem
# repository; production can switch to an S3 repository through environment.
REPOSITORY_NAME = os.getenv("ELASTICSEARCH_SNAPSHOT_REPOSITORY", "backup_repository")
REPOSITORY_TYPE = os.getenv("ELASTICSEARCH_SNAPSHOT_REPOSITORY_TYPE", "fs").strip().lower()
REPOSITORY_PATH = os.getenv("ELASTICSEARCH_SNAPSHOT_PATH", "/usr/share/elasticsearch/backups")
BACKUP_REQUIRED_DEST = os.getenv("BACKUP_REQUIRED_DEST", "prd").strip()
BACKUP_S3_PREFIX = os.getenv("BACKUP_S3_PREFIX", "btaa-geospatial-api").strip("/")

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {text}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean-ish environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def repository_body() -> Optional[Dict[str, Any]]:
    """Build the Elasticsearch snapshot repository body."""
    if REPOSITORY_TYPE == "fs":
        return {
            "type": "fs",
            "settings": {
                "location": REPOSITORY_PATH,
                "compress": True,
            },
        }

    if REPOSITORY_TYPE != "s3":
        print_error(
            "Unsupported ELASTICSEARCH_SNAPSHOT_REPOSITORY_TYPE="
            f"{REPOSITORY_TYPE!r}; expected 'fs' or 's3'"
        )
        return None

    bucket = os.getenv("ELASTICSEARCH_SNAPSHOT_S3_BUCKET") or os.getenv("BACKUP_S3_BUCKET")
    if not bucket:
        print_error(
            "BACKUP_S3_BUCKET or ELASTICSEARCH_SNAPSHOT_S3_BUCKET is required "
            "for S3 Elasticsearch snapshots"
        )
        return None

    base_path = (
        os.getenv("ELASTICSEARCH_SNAPSHOT_S3_BASE_PATH")
        or f"{BACKUP_S3_PREFIX}/{os.getenv('KAMAL_DEST', 'unknown')}/elasticsearch"
    ).strip("/")

    settings: Dict[str, Any] = {
        "bucket": bucket,
        "base_path": base_path,
        "client": os.getenv("ELASTICSEARCH_SNAPSHOT_S3_CLIENT", "default"),
        "compress": True,
    }

    storage_class = os.getenv("ELASTICSEARCH_SNAPSHOT_S3_STORAGE_CLASS")
    if storage_class:
        settings["storage_class"] = storage_class

    if env_bool("ELASTICSEARCH_SNAPSHOT_S3_SERVER_SIDE_ENCRYPTION", default=False):
        settings["server_side_encryption"] = True

    return {
        "type": "s3",
        "settings": settings,
    }


def scheduled_skip_reason() -> Optional[str]:
    """Return why a scheduled backup should skip, or None when it should run."""
    if not env_bool("BACKUP_ENABLED", default=False):
        return "BACKUP_ENABLED is not true"

    destination = os.getenv("KAMAL_DEST", "").strip()
    if BACKUP_REQUIRED_DEST and destination != BACKUP_REQUIRED_DEST:
        return (
            f"KAMAL_DEST={destination or '(unset)'} does not match "
            f"BACKUP_REQUIRED_DEST={BACKUP_REQUIRED_DEST}"
        )

    return None


def managed_snapshot(snapshot: Dict[str, Any]) -> bool:
    """Limit retention cleanup to snapshots produced by this script/index."""
    name = str(snapshot.get("snapshot", ""))
    metadata = snapshot.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("index") == INDEX_NAME:
        return True
    return name.startswith(f"{INDEX_NAME}_snapshot_")


async def ensure_repository(client: AsyncElasticsearch) -> bool:
    """Ensure snapshot repository exists, create if it doesn't."""
    try:
        # Check if repository exists
        await client.snapshot.get_repository(name=REPOSITORY_NAME)
        print_success(f"Repository '{REPOSITORY_NAME}' already exists")
        return True
    except NotFoundError:
        # Repository doesn't exist, create it
        body = repository_body()
        if body is None:
            return False

        if REPOSITORY_TYPE == "fs":
            print_info(f"Creating repository '{REPOSITORY_NAME}' at {REPOSITORY_PATH}")
        else:
            settings = body["settings"]
            print_info(
                f"Creating S3 repository '{REPOSITORY_NAME}' at "
                f"s3://{settings['bucket']}/{settings.get('base_path', '')}"
            )
        try:
            await client.snapshot.create_repository(
                name=REPOSITORY_NAME,
                body=body,
            )
            print_success(f"Repository '{REPOSITORY_NAME}' created successfully")
            return True
        except RequestError as e:
            print_error(f"Failed to create repository: {str(e)}")
            if REPOSITORY_TYPE == "fs":
                print_warning(
                    "Note: The backup directory must exist and be writable by Elasticsearch"
                )
                print_warning(f"Ensure {REPOSITORY_PATH} exists in the ES container or is mounted")
            else:
                print_warning(
                    "For S3 repositories, ensure repository-s3 support is available and "
                    "S3 credentials are configured for the Elasticsearch node"
                )
            return False
    except Exception as e:
        print_error(f"Error checking repository: {str(e)}")
        return False


async def create_snapshot(
    client: AsyncElasticsearch, snapshot_name: Optional[str] = None
) -> Optional[str]:
    """Create a snapshot of the index."""
    if not snapshot_name:
        # Generate snapshot name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"{INDEX_NAME}_snapshot_{timestamp}"

    print_info(f"Creating snapshot '{snapshot_name}' for index '{INDEX_NAME}'")

    try:
        # Create snapshot
        response = await client.snapshot.create(
            repository=REPOSITORY_NAME,
            snapshot=snapshot_name,
            body={
                "indices": INDEX_NAME,
                "ignore_unavailable": False,
                "include_global_state": False,
                "metadata": {
                    "taken_by": "backup_script",
                    "taken_because": "scheduled_backup",
                    "index": INDEX_NAME,
                    "destination": os.getenv("KAMAL_DEST", "unknown"),
                    "repository_type": REPOSITORY_TYPE,
                },
            },
            wait_for_completion=False,  # Don't wait, return immediately
        )

        print_success(f"Snapshot '{snapshot_name}' creation started")
        print_info(f"Snapshot UUID: {response.get('snapshot', 'unknown')}")
        print_info("Use --status to check snapshot progress")
        return snapshot_name

    except RequestError as e:
        print_error(f"Failed to create snapshot: {str(e)}")
        return None
    except Exception as e:
        print_error(f"Unexpected error creating snapshot: {str(e)}")
        return None


async def get_snapshot_status(
    client: AsyncElasticsearch, snapshot_name: str
) -> Optional[Dict[str, Any]]:
    """Get status of a specific snapshot."""
    try:
        response = await client.snapshot.get(repository=REPOSITORY_NAME, snapshot=snapshot_name)
        snapshots = response.get("snapshots", [])
        if snapshots:
            return snapshots[0]
        return None
    except NotFoundError:
        print_error(f"Snapshot '{snapshot_name}' not found")
        return None
    except Exception as e:
        print_error(f"Error getting snapshot status: {str(e)}")
        return None


async def list_snapshots(client: AsyncElasticsearch) -> List[Dict[str, Any]]:
    """List all snapshots in the repository."""
    try:
        response = await client.snapshot.get(repository=REPOSITORY_NAME, snapshot="_all")
        snapshots = response.get("snapshots", [])
        return sorted(snapshots, key=lambda x: x.get("start_time_in_millis", 0), reverse=True)
    except Exception as e:
        print_error(f"Error listing snapshots: {str(e)}")
        return []


async def restore_snapshot(
    client: AsyncElasticsearch,
    snapshot_name: str,
    rename_index: Optional[str] = None,
    wait_for_completion: bool = False,
) -> bool:
    """Restore a snapshot."""
    print_warning("Restoring a snapshot will overwrite the existing index!")
    print_info(f"Snapshot: {snapshot_name}")
    print_info(f"Target index: {INDEX_NAME}")

    try:
        restore_body = {
            "indices": INDEX_NAME,
            "ignore_unavailable": False,
            "include_global_state": False,
        }

        if rename_index:
            restore_body["rename_pattern"] = INDEX_NAME
            restore_body["rename_replacement"] = rename_index
            print_info(f"Will restore to index: {rename_index}")

        await client.snapshot.restore(
            repository=REPOSITORY_NAME,
            snapshot=snapshot_name,
            body=restore_body,
            wait_for_completion=wait_for_completion,
        )

        if wait_for_completion:
            print_success(f"Snapshot '{snapshot_name}' restored successfully")
        else:
            print_success(f"Snapshot '{snapshot_name}' restore started")
            print_info("Restore is running in background. Check index status to monitor progress.")

        return True

    except RequestError as e:
        print_error(f"Failed to restore snapshot: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Unexpected error restoring snapshot: {str(e)}")
        return False


async def delete_snapshot(client: AsyncElasticsearch, snapshot_name: str) -> bool:
    """Delete a snapshot."""
    print_warning(f"Deleting snapshot '{snapshot_name}'")
    try:
        await client.snapshot.delete(repository=REPOSITORY_NAME, snapshot=snapshot_name)
        print_success(f"Snapshot '{snapshot_name}' deleted successfully")
        return True
    except NotFoundError:
        print_error(f"Snapshot '{snapshot_name}' not found")
        return False
    except Exception as e:
        print_error(f"Error deleting snapshot: {str(e)}")
        return False


async def cleanup_old_snapshots(client: AsyncElasticsearch, keep_days: int = 7) -> int:
    """Delete snapshots older than keep_days."""
    print_info(f"Cleaning up snapshots older than {keep_days} days")
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    cutoff_timestamp = int(cutoff_date.timestamp() * 1000)

    snapshots = [
        snapshot for snapshot in await list_snapshots(client) if managed_snapshot(snapshot)
    ]
    deleted_count = 0

    for snapshot in snapshots:
        start_time = snapshot.get("start_time_in_millis", 0)
        snapshot_name = snapshot.get("snapshot", "unknown")
        snapshot_date = datetime.fromtimestamp(start_time / 1000)

        if start_time < cutoff_timestamp:
            print_info(
                f"Deleting old snapshot: {snapshot_name} "
                f"(from {snapshot_date.strftime('%Y-%m-%d %H:%M:%S')})"
            )
            if await delete_snapshot(client, snapshot_name):
                deleted_count += 1
        else:
            print_info(
                f"Keeping snapshot: {snapshot_name} "
                f"(from {snapshot_date.strftime('%Y-%m-%d %H:%M:%S')})"
            )

    return deleted_count


async def cleanup_snapshots_by_count(client: AsyncElasticsearch, retain_count: int) -> int:
    """Keep only the newest N completed snapshots produced by this script."""
    if retain_count < 1:
        raise ValueError("retain_count must be at least 1")

    print_info(f"Keeping newest {retain_count} managed snapshot(s)")
    snapshots = [
        snapshot
        for snapshot in await list_snapshots(client)
        if managed_snapshot(snapshot) and snapshot.get("state") != "IN_PROGRESS"
    ]
    snapshots.sort(key=lambda x: x.get("start_time_in_millis", 0), reverse=True)

    deleted_count = 0
    for snapshot in snapshots[retain_count:]:
        snapshot_name = snapshot.get("snapshot", "unknown")
        print_info(f"Deleting snapshot outside retain-count window: {snapshot_name}")
        if await delete_snapshot(client, snapshot_name):
            deleted_count += 1

    return deleted_count


def format_snapshot_info(snapshot: Dict[str, Any]) -> str:
    """Format snapshot information for display."""
    name = snapshot.get("snapshot", "unknown")
    state = snapshot.get("state", "unknown")
    start_time = snapshot.get("start_time_in_millis", 0)
    end_time = snapshot.get("end_time_in_millis", 0)
    duration_ms = end_time - start_time if end_time > start_time else 0

    if start_time:
        start_date = datetime.fromtimestamp(start_time / 1000)
        date_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        date_str = "unknown"

    state_colors = {
        "SUCCESS": Colors.GREEN,
        "IN_PROGRESS": Colors.YELLOW,
        "FAILED": Colors.RED,
        "PARTIAL": Colors.YELLOW,
    }
    color = state_colors.get(state, Colors.RESET)

    duration_str = f"{duration_ms / 1000:.1f}s" if duration_ms > 0 else "N/A"

    indices = snapshot.get("indices", [])
    indices_str = ", ".join(indices) if indices else "none"

    return (
        f"  {Colors.BOLD}{name}{Colors.RESET}\n"
        f"    State: {color}{state}{Colors.RESET}\n"
        f"    Date: {date_str}\n"
        f"    Duration: {duration_str}\n"
        f"    Indices: {indices_str}"
    )


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Elasticsearch backup and restore utility")
    parser.add_argument("--create", action="store_true", help="Create a new snapshot")
    parser.add_argument("--name", type=str, help="Snapshot name (for create or restore)")
    parser.add_argument("--list", action="store_true", help="List all snapshots")
    parser.add_argument("--status", type=str, help="Get status of a specific snapshot")
    parser.add_argument("--restore", type=str, help="Restore a snapshot (specify snapshot name)")
    parser.add_argument("--restore-to", type=str, help="Restore to a different index name")
    parser.add_argument("--delete", type=str, help="Delete a snapshot")
    parser.add_argument("--cleanup", action="store_true", help="Delete old snapshots")
    parser.add_argument(
        "--keep-days", type=int, default=7, help="Days to keep snapshots (default: 7)"
    )
    parser.add_argument(
        "--retain-count",
        type=int,
        help="Keep only the newest N managed snapshots after create/cleanup",
    )
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Apply BACKUP_ENABLED and KAMAL_DEST production guard before running",
    )
    parser.add_argument("--wait", action="store_true", help="Wait for snapshot/restore to complete")

    args = parser.parse_args()

    # If no action specified, show help
    if not any(
        [
            args.create,
            args.list,
            args.status,
            args.restore,
            args.delete,
            args.cleanup,
            args.retain_count,
        ]
    ):
        parser.print_help()
        return 0

    if args.scheduled:
        skip_reason = scheduled_skip_reason()
        if skip_reason:
            print_info(f"Skipping Elasticsearch snapshot: {skip_reason}")
            return 0

    print_header("Elasticsearch Backup Utility")
    print_info(f"Elasticsearch URL: {ELASTICSEARCH_URL}")
    print_info(f"Index: {INDEX_NAME}")
    print_info(f"Repository: {REPOSITORY_NAME} ({REPOSITORY_TYPE})\n")

    client = AsyncElasticsearch(
        hosts=[ELASTICSEARCH_URL],
        verify_certs=False,
        ssl_show_warn=False,
        request_timeout=60,
        retry_on_timeout=True,
        max_retries=3,
    )

    try:
        # Test connection
        await client.info()

        # Ensure repository exists (needed for most operations)
        if not await ensure_repository(client):
            print_error("Cannot proceed without repository")
            return 1

        # Handle different operations
        if args.create:
            snapshot_name = await create_snapshot(client, args.name)
            snapshot_finished_successfully = snapshot_name is not None and not args.wait
            if snapshot_name is None:
                return 1
            if snapshot_name and args.wait:
                print_info("Waiting for snapshot to complete...")
                # Poll for completion
                import time

                while True:
                    status = await get_snapshot_status(client, snapshot_name)
                    if not status:
                        snapshot_finished_successfully = False
                        break
                    state = status.get("state", "UNKNOWN")
                    if state == "SUCCESS":
                        print_success("Snapshot completed successfully")
                        snapshot_finished_successfully = True
                        break
                    elif state == "FAILED":
                        print_error("Snapshot failed")
                        snapshot_finished_successfully = False
                        break
                    elif state in ["IN_PROGRESS", "INIT"]:
                        print_info(f"Snapshot in progress... ({state})")
                        time.sleep(5)
                    else:
                        print_info(f"Snapshot state: {state}")
                        time.sleep(5)

            if args.retain_count and snapshot_finished_successfully:
                deleted = await cleanup_snapshots_by_count(client, args.retain_count)
                print_success(f"Retain-count cleanup deleted {deleted} old snapshot(s)")
            elif args.wait and not snapshot_finished_successfully:
                return 1

        elif args.list:
            print_header("Available Snapshots")
            snapshots = await list_snapshots(client)
            if snapshots:
                for snapshot in snapshots:
                    print(format_snapshot_info(snapshot))
                    print()
            else:
                print_info("No snapshots found")

        elif args.status:
            status = await get_snapshot_status(client, args.status)
            if status:
                print_header(f"Snapshot Status: {args.status}")
                print(format_snapshot_info(status))
            else:
                print_error(f"Could not get status for snapshot '{args.status}'")

        elif args.restore:
            restore_index = args.restore_to if args.restore_to else None
            restored = await restore_snapshot(
                client, args.restore, rename_index=restore_index, wait_for_completion=args.wait
            )
            if not restored:
                return 1

        elif args.delete:
            deleted = await delete_snapshot(client, args.delete)
            if not deleted:
                return 1

        elif args.cleanup:
            if args.retain_count:
                deleted = await cleanup_snapshots_by_count(client, args.retain_count)
            else:
                deleted = await cleanup_old_snapshots(client, args.keep_days)
            print_success(f"Cleaned up {deleted} old snapshot(s)")

        elif args.retain_count:
            deleted = await cleanup_snapshots_by_count(client, args.retain_count)
            print_success(f"Retain-count cleanup deleted {deleted} old snapshot(s)")

        return 0

    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
