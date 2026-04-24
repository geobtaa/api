#!/usr/bin/env python3
"""
Setup script for API rate limiting system.

This script:
1. Creates the API rate limiting tables (api_service_tiers, api_keys, analytics_api_usage_logs)
2. Initializes the six service tiers with their rate limits

Run this script after setting up your database to enable rate limiting.
"""

import logging
import sys
from pathlib import Path

# Add the project root directory to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from db.migrations.create_api_rate_limiting_tables import create_api_rate_limiting_tables
from db.migrations.initialize_api_tiers import initialize_api_tiers

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Run both migration steps."""
    try:
        logger.info("=" * 60)
        logger.info("Setting up API Rate Limiting System")
        logger.info("=" * 60)

        # Step 1: Create tables
        logger.info("\nStep 1: Creating API rate limiting tables...")
        create_api_rate_limiting_tables()
        logger.info("✓ Tables created successfully")

        # Step 2: Initialize tiers
        logger.info("\nStep 2: Initializing service tiers...")
        initialize_api_tiers()
        logger.info("✓ Tiers initialized successfully")

        logger.info("\n" + "=" * 60)
        logger.info("API Rate Limiting setup complete!")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Ensure RATE_LIMIT_ENABLED=true in your .env file")
        logger.info("2. Ensure RATE_LIMIT_REDIS_DB=2 in your .env file")
        logger.info("3. Restart your API server")
        logger.info("4. Create API keys via POST /api/v1/admin/api-keys")

    except Exception as e:
        logger.error(f"\n❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
