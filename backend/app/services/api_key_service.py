import hashlib
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from db.async_engine import create_app_async_engine
from db.config import DATABASE_URL
from db.models import api_keys, api_service_tiers

logger = logging.getLogger(__name__)
API_KEY_HASH_ITERATIONS = 600_000
DEFAULT_API_KEY_HASH_SECRET = "btaa-api-key-hash-v2"
API_KEY_TIER_CACHE_TTL_SECONDS = float(os.getenv("API_KEY_TIER_CACHE_TTL_SECONDS", "60"))
API_KEY_LAST_USED_UPDATE_INTERVAL_SECONDS = float(
    os.getenv("API_KEY_LAST_USED_UPDATE_INTERVAL_SECONDS", "60")
)
API_KEY_TIER_CACHE_MAX_ENTRIES = int(os.getenv("API_KEY_TIER_CACHE_MAX_ENTRIES", "2048"))

_tier_cache: dict[str, tuple[float, Dict[str, Any]]] = {}
_anonymous_tier_cache: tuple[float, Dict[str, Any]] | None = None
_last_used_updates: dict[int, float] = {}

# Dedicated async engine/session for API key operations.
engine = create_app_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class APIKeyService:
    """Service to handle API key operations (keys + tiers)."""

    @staticmethod
    def clear_cache() -> None:
        """Clear process-local tier caches.

        Other worker processes naturally refresh when their short TTLs expire.
        """
        global _anonymous_tier_cache
        _tier_cache.clear()
        _last_used_updates.clear()
        _anonymous_tier_cache = None

    @staticmethod
    def _cache_lookup_key(key: str) -> str:
        """Build a non-secret cache key without running the expensive PBKDF2 hash."""
        return APIKeyService.legacy_hash_api_key(key)

    @staticmethod
    def _request_ip_allowed(allowed_ips: Any, request_ip: Optional[str]) -> bool:
        if allowed_ips and request_ip:
            if isinstance(allowed_ips, list):
                if request_ip not in allowed_ips:
                    logger.warning(
                        "API key rejected because the request IP is not in the configured whitelist"
                    )
                    return False
            else:
                logger.warning("API key has an invalid allowed_ips format")
        return True

    @staticmethod
    def _get_cached_tier(cache_key: str, request_ip: Optional[str]) -> Optional[Dict[str, Any]]:
        if API_KEY_TIER_CACHE_TTL_SECONDS <= 0:
            return None
        cached = _tier_cache.get(cache_key)
        if cached is None:
            return None

        expires_at, tier_info = cached
        if expires_at <= time.monotonic():
            _tier_cache.pop(cache_key, None)
            return None
        if not APIKeyService._request_ip_allowed(tier_info.get("allowed_ips"), request_ip):
            return None
        return dict(tier_info)

    @staticmethod
    def _set_cached_tier(cache_key: str, tier_info: Dict[str, Any]) -> None:
        if API_KEY_TIER_CACHE_TTL_SECONDS <= 0:
            return

        now = time.monotonic()
        for key, (expires_at, _) in list(_tier_cache.items()):
            if expires_at <= now:
                _tier_cache.pop(key, None)

        max_entries = max(API_KEY_TIER_CACHE_MAX_ENTRIES, 1)
        while len(_tier_cache) >= max_entries:
            oldest_key = next(iter(_tier_cache))
            _tier_cache.pop(oldest_key, None)

        _tier_cache[cache_key] = (now + API_KEY_TIER_CACHE_TTL_SECONDS, dict(tier_info))

    @staticmethod
    def _get_cached_anonymous_tier() -> Optional[Dict[str, Any]]:
        if API_KEY_TIER_CACHE_TTL_SECONDS <= 0 or _anonymous_tier_cache is None:
            return None

        expires_at, tier_info = _anonymous_tier_cache
        if expires_at <= time.monotonic():
            APIKeyService.clear_cache()
            return None
        return dict(tier_info)

    @staticmethod
    def _set_cached_anonymous_tier(tier_info: Dict[str, Any]) -> None:
        global _anonymous_tier_cache
        if API_KEY_TIER_CACHE_TTL_SECONDS <= 0:
            return
        _anonymous_tier_cache = (
            time.monotonic() + API_KEY_TIER_CACHE_TTL_SECONDS,
            dict(tier_info),
        )

    @staticmethod
    def _last_used_update_due(api_key_id: int) -> bool:
        if API_KEY_LAST_USED_UPDATE_INTERVAL_SECONDS <= 0:
            return True

        now = time.monotonic()
        last_update = _last_used_updates.get(api_key_id)
        return last_update is None or now - last_update >= API_KEY_LAST_USED_UPDATE_INTERVAL_SECONDS

    @staticmethod
    def _remember_last_used_update(api_key_id: int) -> None:
        _last_used_updates[api_key_id] = time.monotonic()

    @staticmethod
    def generate_api_key() -> str:
        """Generate a new API key (UUID v4)."""
        return str(uuid.uuid4())

    @staticmethod
    def hash_api_key(key: str) -> str:
        """Hash an API key using PBKDF2-HMAC-SHA256."""
        salt = (
            os.getenv("API_KEY_HASH_SECRET")
            or os.getenv("SECRET_KEY")
            or DEFAULT_API_KEY_HASH_SECRET
        ).encode("utf-8")
        return hashlib.pbkdf2_hmac(
            "sha256",
            key.encode("utf-8"),
            salt,
            API_KEY_HASH_ITERATIONS,
            dklen=32,
        ).hex()

    @staticmethod
    def legacy_hash_api_key(key: str) -> str:
        """Legacy SHA-256 hash for backward compatibility with stored keys."""
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    async def validate_api_key(
        self, key: str, request_ip: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Validate an API key and return tier information.

        Args:
            key: The API key to validate
            request_ip: The IP address of the requesting client (optional, for IP whitelist checks)

        Returns:
            A dict with tier info if valid, None otherwise.
            Returns None if key is invalid, inactive, or if IP restriction fails.
        """
        cache_key = self._cache_lookup_key(key)
        cached_tier = self._get_cached_tier(cache_key, request_ip)
        if cached_tier is not None:
            return cached_tier

        key_hash = self.hash_api_key(key)
        legacy_key_hash = self.legacy_hash_api_key(key)
        candidate_hashes = [key_hash]
        if legacy_key_hash != key_hash:
            candidate_hashes.append(legacy_key_hash)

        async with async_session() as session:
            try:
                stmt = (
                    select(api_keys, api_service_tiers)
                    .join(api_service_tiers, api_keys.c.tier_id == api_service_tiers.c.id)
                    .where(api_keys.c.key_hash.in_(candidate_hashes))
                    .where(api_keys.c.is_active)
                )
                result = await session.execute(stmt)
                row = result.first()

                if row is None:
                    return None

                m = row._mapping
                api_key_id = m[api_keys.c.id]
                allowed_ips = m[api_keys.c.allowed_ips]
                stored_key_hash = m[api_keys.c.key_hash]

                # Check IP whitelist if configured
                if not self._request_ip_allowed(allowed_ips, request_ip):
                    return None

                tier_info = {
                    "tier_id": m[api_service_tiers.c.id],
                    "tier_name": m[api_service_tiers.c.tier_name],
                    "display_name": m[api_service_tiers.c.display_name],
                    "requests_per_minute": m[api_service_tiers.c.requests_per_minute],
                    "api_key_id": api_key_id,
                    "key_hash": key_hash,
                    "allowed_ips": allowed_ips,
                }

                update_values = {"last_used_at": datetime.utcnow()}
                if stored_key_hash == legacy_key_hash and stored_key_hash != key_hash:
                    update_values["key_hash"] = key_hash
                elif not self._last_used_update_due(api_key_id):
                    update_values = {}

                if update_values:
                    await session.execute(
                        api_keys.update().where(api_keys.c.id == api_key_id).values(**update_values)
                    )
                    await session.commit()
                    self._remember_last_used_update(api_key_id)

                self._set_cached_tier(cache_key, tier_info)
                return tier_info

            except Exception as e:
                logger.error(f"Error validating API key: {e}", exc_info=True)
                return None

    async def get_tier_for_key(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Get tier information for a key hash.

        Returns a dict with tier info if found, None otherwise.
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

                m = row._mapping
                return {
                    "tier_id": m[api_service_tiers.c.id],
                    "tier_name": m[api_service_tiers.c.tier_name],
                    "display_name": m[api_service_tiers.c.display_name],
                    "requests_per_minute": m[api_service_tiers.c.requests_per_minute],
                    "api_key_id": m[api_keys.c.id],
                }

            except Exception as e:
                logger.error(f"Error getting tier for key: {e}", exc_info=True)
                return None

    async def create_api_key(
        self,
        tier_name: str,
        name: Optional[str] = None,
        allowed_ips: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a new API key for the given tier name.

        Args:
            tier_name: Name of the service tier
            name: Optional friendly name for the key
            allowed_ips: Optional list of allowed IP addresses (empty list means no restriction)

        Returns:
            A dict with `api_key`, `key_id`, and `tier_name` if successful,
            or None on error.
        """
        async with async_session() as session:
            try:
                # Resolve tier ID by name
                stmt = select(api_service_tiers.c.id).where(
                    api_service_tiers.c.tier_name == tier_name
                )
                result = await session.execute(stmt)
                tier = result.first()

                if tier is None:
                    logger.error(f"Tier '{tier_name}' not found")
                    return None

                tier_id = tier[0]

                # Generate new key
                api_key = self.generate_api_key()
                key_hash = self.hash_api_key(api_key)

                # Insert into database, including timestamps
                now = datetime.utcnow()
                insert_values = {
                    "key_hash": key_hash,
                    "tier_id": tier_id,
                    "name": name,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }

                # Store allowed_ips as JSON (None if not provided or empty list)
                if allowed_ips:
                    insert_values["allowed_ips"] = allowed_ips
                else:
                    insert_values["allowed_ips"] = None

                insert_stmt = api_keys.insert().values(**insert_values).returning(api_keys.c.id)

                result = await session.execute(insert_stmt)
                key_id = result.scalar_one_or_none()
                await session.commit()

                logger.info(f"Created API key with ID {key_id} for tier {tier_name}")
                self.clear_cache()

                return {
                    "api_key": api_key,  # Only shown once!
                    "key_id": key_id,
                    "tier_name": tier_name,
                }

            except Exception as e:
                logger.error(f"Error creating API key: {e}", exc_info=True)
                await session.rollback()
                return None

    async def revoke_api_key(self, key_hash: str) -> bool:
        """Revoke (deactivate) an API key by its hash.

        Returns True if a row was updated, False otherwise.
        """
        async with async_session() as session:
            try:
                stmt = (
                    api_keys.update().where(api_keys.c.key_hash == key_hash).values(is_active=False)
                )
                result = await session.execute(stmt)
                await session.commit()

                self.clear_cache()
                return result.rowcount > 0

            except Exception as e:
                logger.error(f"Error revoking API key: {e}", exc_info=True)
                await session.rollback()
                return False

    async def revoke_api_key_by_id(self, key_id: int) -> bool:
        """Revoke an API key by database id, avoiding shared-connection issues."""
        async with async_session() as session:
            try:
                stmt = select(api_keys.c.key_hash).where(api_keys.c.id == key_id)
                result = await session.execute(stmt)
                row = result.first()
                if row is None:
                    return False
                key_hash = row[0]
            except Exception as e:
                logger.error(f"Error fetching API key hash for id={key_id}: {e}", exc_info=True)
                await session.rollback()
                return False

        # Delegate to revoke by hash (uses a fresh session with NullPool)
        return await self.revoke_api_key(key_hash)

    async def get_anonymous_tier(self) -> Optional[Dict[str, Any]]:
        """Get the anonymous tier information.

        Returns a dict with tier info if found, None otherwise.
        """
        cached_tier = self._get_cached_anonymous_tier()
        if cached_tier is not None:
            return cached_tier

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

                tier_info = {
                    "tier_id": row[0],
                    "tier_name": row[1],
                    "display_name": row[2],
                    "requests_per_minute": row[3],
                }
                self._set_cached_anonymous_tier(tier_info)
                return tier_info

            except Exception as e:
                logger.error(f"Error getting anonymous tier: {e}", exc_info=True)
                return None

    async def list_api_keys(self) -> List[Dict[str, Any]]:
        """List all API keys with their associated tier information."""
        async with async_session() as session:
            try:
                stmt = (
                    select(
                        api_keys.c.id.label("key_id"),
                        api_keys.c.key_hash,
                        api_service_tiers.c.tier_name,
                        api_service_tiers.c.display_name.label("tier_display_name"),
                        api_keys.c.name,
                        api_keys.c.is_active,
                        api_keys.c.created_at,
                        api_keys.c.last_used_at,
                        api_keys.c.allowed_ips,
                    )
                    .join(api_service_tiers, api_keys.c.tier_id == api_service_tiers.c.id)
                    .order_by(api_keys.c.created_at.desc())
                )
                result = await session.execute(stmt)
                rows = result.all()

                keys: List[Dict[str, Any]] = []
                for row in rows:
                    m = row._mapping
                    keys.append(
                        {
                            "id": m["key_id"],
                            "key_hash": (m["key_hash"] or "")[:16] + "...",
                            "tier_name": m["tier_name"],
                            "tier_display_name": m["tier_display_name"],
                            "name": m["name"],
                            "is_active": m["is_active"],
                            "created_at": m["created_at"].isoformat() if m["created_at"] else None,
                            "last_used_at": m["last_used_at"].isoformat()
                            if m["last_used_at"]
                            else None,
                            "allowed_ips": m["allowed_ips"],  # Include IP whitelist
                        }
                    )

                return keys
            except Exception as e:
                logger.error(f"Error listing API keys: {e}", exc_info=True)
                return []

    async def update_api_key_by_id(
        self,
        key_id: int,
        tier_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        name: Optional[str] = None,
        allowed_ips: Optional[List[str]] = None,
    ) -> bool:
        """Update an existing API key by ID.

        Args:
            key_id: The ID of the key to update
            tier_name: Optional new tier name
            is_active: Optional active status
            name: Optional friendly name
            allowed_ips: Optional list of allowed IPs (empty list removes restriction,
                None means no change)

        Returns:
            True if the key was updated, False otherwise.
        """
        async with async_session() as session:
            try:
                # Ensure key exists
                stmt = select(api_keys.c.id).where(api_keys.c.id == key_id)
                result = await session.execute(stmt)
                existing = result.first()
                if existing is None:
                    return False

                update_values: Dict[str, Any] = {}

                if tier_name is not None:
                    tier_stmt = select(api_service_tiers.c.id).where(
                        api_service_tiers.c.tier_name == tier_name
                    )
                    tier_result = await session.execute(tier_stmt)
                    tier_row = tier_result.first()
                    if tier_row is None:
                        logger.error(f"Tier '{tier_name}' not found for update")
                        return False
                    update_values["tier_id"] = tier_row[0]

                if is_active is not None:
                    update_values["is_active"] = is_active

                if name is not None:
                    update_values["name"] = name

                # Handle allowed_ips update
                # Use a sentinel to distinguish between "not provided" and "set to empty"
                # In Pydantic, we'll use a special value or check if it's in the request
                # For now, we'll use None to mean "don't change" and [] to mean "remove restriction"
                # Actually, we need to handle this differently - we can't distinguish between
                # "not provided" and "set to empty" with Optional. Let's use a different approach:
                # We'll check if it's been explicitly set in the endpoint layer.
                # For now, if it's an empty list, set to None (no restriction)
                if allowed_ips is not None:
                    if allowed_ips:
                        update_values["allowed_ips"] = allowed_ips
                    else:
                        # Empty list means remove restriction
                        update_values["allowed_ips"] = None

                if not update_values:
                    # Nothing to update
                    return False

                # Always update updated_at timestamp
                update_values["updated_at"] = datetime.utcnow()

                update_stmt = (
                    api_keys.update().where(api_keys.c.id == key_id).values(**update_values)
                )
                await session.execute(update_stmt)
                await session.commit()
                self.clear_cache()
                return True
            except Exception as e:
                logger.error(f"Error updating API key id={key_id}: {e}", exc_info=True)
                await session.rollback()
                return False

    async def list_tiers(self) -> List[Dict[str, Any]]:
        """List all service tiers."""
        async with async_session() as session:
            try:
                stmt = select(
                    api_service_tiers.c.id,
                    api_service_tiers.c.tier_name,
                    api_service_tiers.c.display_name,
                    api_service_tiers.c.requests_per_minute,
                    api_service_tiers.c.description,
                ).order_by(api_service_tiers.c.id)

                result = await session.execute(stmt)
                rows = result.all()

                tiers: List[Dict[str, Any]] = []
                for row in rows:
                    tiers.append(
                        {
                            "id": row[0],
                            "tier_name": row[1],
                            "display_name": row[2],
                            "requests_per_minute": row[3],
                            "description": row[4],
                        }
                    )

                return tiers
            except Exception as e:
                logger.error(f"Error listing API tiers: {e}", exc_info=True)
                return []
