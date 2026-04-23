"""Unified API rate limiting schema + seed initializer.

This module provides a single entrypoint that:

1. Creates the API rate limiting tables (api_service_tiers, api_keys, analytics_api_usage_logs)
2. Seeds the six default service tiers

It delegates to the existing migration helpers.
"""

from db.migrations.create_api_rate_limiting_tables import create_api_rate_limiting_tables
from db.migrations.initialize_api_tiers import initialize_api_tiers


def init_api_rate_limiting() -> None:
    """Create API rate limiting tables and seed default tiers.

    This function is idempotent and safe to call multiple times.
    """
    create_api_rate_limiting_tables()
    initialize_api_tiers()
