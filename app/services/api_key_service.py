import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.config import DATABASE_URL
from db.models import api_keys, api_service_tiers

logger = logging.getLogger(__name__)

# Create async engine and session
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class APIKeyService:
    """Service to handle API key operations."""

    @staticmethod
    def generate_api_key() -> str:
        """Generate a new API key (UUID v4)."""
        return str(uuid.uuid4())

    @staticmethod
    def hash_api_key(key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(key.encode()).hexdigest()

    async def validate_api_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return tier information.

        Args:
            key: The API key to validate

        Returns:
            Dictionary with tier info if valid, None otherwise
        """
        key_hash = self.hash_api_key(key)

        async with async_session() as session:
            try:
                # Join with tiers table to get tier info
                stmt = (
                    select(api_keys, api_service_tiers)
                    .join(api_service_tiers, api_keys.c.tier_id == api_service_tiers.c.id)
                    .where(api_keys.c.key_hash == key_hash)
                    .where(api_keys.c.is_active)
                )

                result = await session.execute(stmt)
                row = result.first()

                if row is None:
                    return None

                # Extract tier information
                tier_info = {
                    "tier_id": row[api_service_tiers.c.id],
                    "tier_name": row[api_service_tiers.c.tier_name],
                    "display_name": row[api_service_tiers.c.display_name],
                    "requests_per_minute": row[api_service_tiers.c.requests_per_minute],
                    "api_key_id": row[api_keys.c.id],
                    "key_hash": key_hash,
                }

                # Update last_used_at
                await session.execute(
                    api_keys.update()
                    .where(api_keys.c.id == row[api_keys.c.id])
                    .values(last_used_at=datetime.utcnow())
                )
                await session.commit()

                return tier_info

            except Exception as e:
                logger.error(f"Error validating API key: {e}")
                return None

    async def get_tier_for_key(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get tier information for a key hash.

        Args:
            key_hash: The hashed API key

        Returns:
            Dictionary with tier info if found, None otherwise
        """
        async with async_session() as session:
            try:
                stmt = (
                    select(api_keys, api_service_tiers)
                    .join(api_service_tiers, api_keys.c.tier_id == api_service_tiers.c.id)
                    .where(api_keys.c.key_hash == key_hash)
                    .where(api_keys.c.is_active)
                )

                result = await session.execute(stmt)
                row = result.first()

                if row is None:
                    return None

                return {
                    "tier_id": row[api_service_tiers.c.id],
                    "tier_name": row[api_service_tiers.c.tier_name],
                    "display_name": row[api_service_tiers.c.display_name],
                    "requests_per_minute": row[api_service_tiers.c.requests_per_minute],
                    "api_key_id": row[api_keys.c.id],
                }

            except Exception as e:
                logger.error(f"Error getting tier for key: {e}")
                return None

    async def create_api_key(
        self, tier_name: str, name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new API key.

        Args:
            tier_name: Name of the tier to assign
            name: Optional name/description for the key

        Returns:
            Dictionary with api_key, key_id, tier_name if successful, None otherwise
        """
        async with async_session() as session:
            try:
                # Get tier ID
                stmt = select(api_service_tiers.c.id).where(
                    api_service_tiers.c.tier_name == tier_name
                )
                result = await session.execute(stmt)
                tier = result.first()

                if tier is None:
                    logger.error(f"Tier '{tier_name}' not found")
                    return None

                tier_id = tier[0]  # First (and only) column is id

                # Generate new key
                api_key = self.generate_api_key()
                key_hash = self.hash_api_key(api_key)

                # Insert into database
                stmt = api_keys.insert().values(
                    key_hash=key_hash,
                    tier_id=tier_id,
                    name=name,
                    is_active=True,
                )

                result = await session.execute(stmt)
                key_id = result.inserted_primary_key[0]
                await session.commit()

                logger.info(f"Created API key with ID {key_id} for tier {tier_name}")

                return {
                    "api_key": api_key,  # Only shown once!
                    "key_id": key_id,
                    "tier_name": tier_name,
                }

            except Exception as e:
                logger.error(f"Error creating API key: {e}")
                await session.rollback()
                return None

    async def revoke_api_key(self, key_hash: str) -> bool:
        """
        Revoke (deactivate) an API key.

        Args:
            key_hash: The hashed API key

        Returns:
            True if successful, False otherwise
        """
        async with async_session() as session:
            try:
                stmt = (
                    api_keys.update().where(api_keys.c.key_hash == key_hash).values(is_active=False)
                )

                result = await session.execute(stmt)
                await session.commit()

                return result.rowcount > 0

            except Exception as e:
                logger.error(f"Error revoking API key: {e}")
                await session.rollback()
                return False

    async def get_anonymous_tier(self) -> Optional[Dict[str, Any]]:
        """
        Get the anonymous tier information.

        Returns:
            Dictionary with tier info if found, None otherwise
        """
        async with async_session() as session:
            try:
                stmt = select(
                    api_service_tiers.c.id,
                    api_service_tiers.c.tier_name,
                    api_service_tiers.c.display_name,
                    api_service_tiers.c.requests_per_minute,
                ).where(api_service_tiers.c.tier_name == "anonymous")
                result = await session.execute(stmt)
                row = result.first()

                if row is None:
                    return None

                # Access by column index (order matches select statement)
                return {
                    "tier_id": row[0],
                    "tier_name": row[1],
                    "display_name": row[2],
                    "requests_per_minute": row[3],
                }

            except Exception as e:
                logger.error(f"Error getting anonymous tier: {e}", exc_info=True)
                return None
