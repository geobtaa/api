#!/usr/bin/env python3
"""
Regenerate API keys created before PBKDF2 hashing change.

Keys created before 2026-01-20 need to be regenerated because they use
SHA-256 hashing, which is no longer supported after commit 3ab29b0.

This script:
1. Lists all existing API keys
2. Identifies keys created before the PBKDF2 change date
3. Creates replacement keys with identical tier/settings
4. Optionally deactivates old keys
5. Outputs a migration report
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List

from dotenv import load_dotenv

# Add backend/ to import path (scripts/ is under backend/scripts/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.api_key_service import APIKeyService  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Default cutoff date: when PBKDF2 was introduced (commit 3ab29b0)
DEFAULT_CUTOFF_DATE = datetime(2026, 1, 20)


async def regenerate_api_keys(
    cutoff_date: datetime,
    dry_run: bool = False,
    deactivate_old: bool = False,
) -> Dict[str, any]:
    """Regenerate API keys created before the cutoff date.

    Args:
        cutoff_date: Keys created before this date will be regenerated
        dry_run: If True, only show what would be done without making changes
        deactivate_old: If True, deactivate old keys after creating replacements

    Returns:
        Dictionary with migration results and statistics
    """
    api_key_service = APIKeyService()

    # Get all API keys
    logger.info("Fetching all API keys...")
    all_keys = await api_key_service.list_api_keys()
    logger.info(f"Found {len(all_keys)} total API keys")

    # Identify keys that need regeneration
    keys_to_regenerate: List[Dict] = []
    for key in all_keys:
        if not key.get("created_at"):
            logger.warning(f"Key {key.get('id')} has no created_at date, skipping")
            continue

        try:
            created_at = datetime.fromisoformat(key["created_at"].replace("Z", "+00:00"))
            # Remove timezone for comparison
            if created_at.tzinfo:
                created_at = created_at.replace(tzinfo=None)
        except (ValueError, AttributeError) as e:
            logger.warning(
                f"Key {key.get('id')} has invalid created_at date '{key.get('created_at')}': {e}"
            )
            continue

        if created_at < cutoff_date:
            keys_to_regenerate.append(key)

    logger.info(
        f"Found {len(keys_to_regenerate)} keys created before {cutoff_date.date()} "
        f"that need regeneration"
    )

    if not keys_to_regenerate:
        logger.info("No keys need regeneration. All keys are using PBKDF2 hashing.")
        return {
            "total_keys": len(all_keys),
            "keys_to_regenerate": 0,
            "regenerated": 0,
            "failed": 0,
            "migrations": [],
        }

    # Process each key
    migrations: List[Dict] = []
    successful = 0
    failed = 0

    for old_key in keys_to_regenerate:
        key_id = old_key["id"]
        tier_name = old_key["tier_name"]
        name = old_key.get("name")
        allowed_ips = old_key.get("allowed_ips")

        logger.info(f"Processing key ID {key_id} (tier: {tier_name}, name: {name or 'unnamed'})")

        if dry_run:
            logger.info(f"  [DRY RUN] Would create replacement key for key ID {key_id}")
            migrations.append(
                {
                    "old_key_id": key_id,
                    "old_key_name": name,
                    "tier_name": tier_name,
                    "status": "would_regenerate",
                    "new_api_key": None,
                    "new_key_id": None,
                    "error": None,
                }
            )
            continue

        try:
            # Create replacement key with same settings
            result = await api_key_service.create_api_key(
                tier_name=tier_name,
                name=name,
                allowed_ips=allowed_ips if allowed_ips else None,
            )

            if result is None:
                error_msg = f"Failed to create replacement key for key ID {key_id}"
                logger.error(error_msg)
                migrations.append(
                    {
                        "old_key_id": key_id,
                        "old_key_name": name,
                        "tier_name": tier_name,
                        "status": "failed",
                        "new_api_key": None,
                        "new_key_id": None,
                        "error": error_msg,
                    }
                )
                failed += 1
                continue

            new_api_key = result["api_key"]
            new_key_id = result["key_id"]

            logger.info(f"  ✓ Created replacement key ID {new_key_id} for old key ID {key_id}")
            # Note: API key is not logged for security - see report output instead

            # Optionally deactivate old key
            if deactivate_old:
                deactivated = await api_key_service.revoke_api_key_by_id(key_id)
                if deactivated:
                    logger.info(f"  ✓ Deactivated old key ID {key_id}")
                else:
                    logger.warning(f"  ⚠ Failed to deactivate old key ID {key_id}")

            migrations.append(
                {
                    "old_key_id": key_id,
                    "old_key_name": name,
                    "tier_name": tier_name,
                    "status": "regenerated",
                    "new_api_key": new_api_key,
                    "new_key_id": new_key_id,
                    "error": None,
                }
            )
            successful += 1

        except Exception as e:
            error_msg = f"Error regenerating key ID {key_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            migrations.append(
                {
                    "old_key_id": key_id,
                    "old_key_name": name,
                    "tier_name": tier_name,
                    "status": "error",
                    "new_api_key": None,
                    "new_key_id": None,
                    "error": error_msg,
                }
            )
            failed += 1

    return {
        "total_keys": len(all_keys),
        "keys_to_regenerate": len(keys_to_regenerate),
        "regenerated": successful,
        "failed": failed,
        "migrations": migrations,
    }


def print_report(results: Dict) -> None:
    """Print a human-readable migration report."""
    print("\n" + "=" * 80)
    print("API Key Regeneration Report")
    print("=" * 80)
    print(f"Total API keys found: {results['total_keys']}")
    print(f"Keys needing regeneration: {results['keys_to_regenerate']}")
    print(f"Successfully regenerated: {results['regenerated']}")
    print(f"Failed: {results['failed']}")
    print("\n" + "-" * 80)

    if results["migrations"]:
        print("\nMigration Details:")
        print("-" * 80)
        for migration in results["migrations"]:
            status = migration["status"]
            old_id = migration["old_key_id"]
            old_name = migration["old_key_name"] or "unnamed"
            tier = migration["tier_name"]

            if status == "would_regenerate":
                print(f"  [DRY RUN] Key ID {old_id} ({old_name}, tier: {tier})")
            elif status == "regenerated":
                new_id = migration["new_key_id"]
                new_key = migration["new_api_key"]
                print(f"  ✓ Key ID {old_id} ({old_name}, tier: {tier})")
                print(f"    → New Key ID: {new_id}")
                print(f"    → New API Key: {new_key}")
            elif status == "failed" or status == "error":
                error = migration["error"]
                print(f"  ✗ Key ID {old_id} ({old_name}, tier: {tier})")
                print(f"    Error: {error}")

    print("\n" + "=" * 80)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Regenerate API keys created before PBKDF2 hashing change"
    )
    parser.add_argument(
        "--cutoff-date",
        type=str,
        default="2026-01-20",
        help="Keys created before this date will be regenerated (YYYY-MM-DD, default: 2026-01-20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be regenerated without making changes",
    )
    parser.add_argument(
        "--deactivate-old",
        action="store_true",
        help="Deactivate old keys after creating replacements",
    )

    args = parser.parse_args()

    # Parse cutoff date
    try:
        cutoff_date = datetime.strptime(args.cutoff_date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid cutoff date format: {args.cutoff_date}. Use YYYY-MM-DD")
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN MODE: No changes will be made")
    if args.deactivate_old:
        logger.info("Old keys will be deactivated after creating replacements")

    logger.info(f"Cutoff date: {cutoff_date.date()}")

    try:
        results = await regenerate_api_keys(
            cutoff_date=cutoff_date,
            dry_run=args.dry_run,
            deactivate_old=args.deactivate_old,
        )

        print_report(results)

        # Exit with error code if there were failures
        if results["failed"] > 0:
            logger.warning(f"Migration completed with {results['failed']} failures")
            sys.exit(1)
        elif results["keys_to_regenerate"] > 0:
            logger.info("Migration completed successfully")
        else:
            logger.info("No keys needed regeneration")

    except Exception as e:
        logger.error(f"Fatal error during migration: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
