import logging
import os
import time
from typing import Optional, Tuple

import redis.asyncio as redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Get Redis connection parameters for rate limiting
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
RATE_LIMIT_REDIS_DB = int(os.getenv("RATE_LIMIT_REDIS_DB", "2"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)


class RateLimitService:
    """Service to handle rate limiting using Redis."""

    _instance = None
    _redis_client = None

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (used in tests to avoid cross-test leakage)."""
        cls._instance = None
        cls._redis_client = None

    def __new__(cls):
        """Singleton pattern to avoid multiple Redis connections."""
        if cls._instance is None:
            cls._instance = super(RateLimitService, cls).__new__(cls)
            cls._instance._init_redis_client()
        return cls._instance

    def _init_redis_client(self):
        """Initialize Redis client."""
        try:
            logger.info(
                f"Initializing Redis client for rate limiting on "
                f"{REDIS_HOST}:{REDIS_PORT}, DB {RATE_LIMIT_REDIS_DB}"
            )
            self._redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=RATE_LIMIT_REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Redis client for rate limiting: {e}")
            self._redis_client = None

    async def check_rate_limit(
        self, tier_name: str, identifier: str, requests_per_minute: Optional[int]
    ) -> Tuple[bool, int, int]:
        """
        Check if a request is allowed based on rate limit.

        Args:
            tier_name: Name of the service tier
            identifier: Unique identifier (e.g., API key hash or IP address)
            requests_per_minute: Rate limit (None for unlimited)

        Returns:
            Tuple of (allowed: bool, remaining: int, reset_time: int)
        """
        # If unlimited tier, always allow
        if requests_per_minute is None:
            return True, -1, int(time.time()) + 60  # -1 indicates unlimited

        if self._redis_client is None:
            logger.warning("Redis client not available, allowing request")
            return True, requests_per_minute, int(time.time()) + 60

        try:
            redis_key = f"rate_limit:{tier_name}:{identifier}"
            current_minute = int(time.time() // 60)
            window_key = f"{redis_key}:{current_minute}"

            # Get current count
            count = await self._redis_client.get(window_key)
            current_count = int(count) if count else 0

            # Check if limit exceeded
            if current_count >= requests_per_minute:
                # Calculate reset time (start of next minute)
                reset_time = (current_minute + 1) * 60
                remaining = 0
                return False, remaining, reset_time

            # Increment counter
            await self._redis_client.incr(window_key)
            await self._redis_client.expire(window_key, 60)  # Expire after 60 seconds

            remaining = requests_per_minute - current_count - 1
            reset_time = (current_minute + 1) * 60

            return True, remaining, reset_time

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # On error, allow the request
            return True, requests_per_minute, int(time.time()) + 60

    async def get_rate_limit_headers(
        self,
        tier_name: str,
        identifier: str,
        requests_per_minute: Optional[int],
        remaining: Optional[int] = None,
        reset_time: Optional[int] = None,
    ) -> dict:
        """
        Get rate limit headers for a request.

        Args:
            tier_name: Name of the service tier
            identifier: Unique identifier
            requests_per_minute: Rate limit (None for unlimited)
            remaining: Remaining requests (if already calculated)
            reset_time: Reset time (if already calculated)

        Returns:
            Dictionary with rate limit headers
        """
        # Handle unlimited tier (None means unlimited)
        # Explicitly check for None using 'is None' (not falsy check, since 0 is a valid limit)
        # This check must come first before any type validation
        # Use explicit None check to avoid any potential issues with mock objects or proxies
        if requests_per_minute is None:
            return {
                "X-RateLimit-Limit": "unlimited",
                "X-RateLimit-Remaining": "unlimited",
                "X-RateLimit-Reset": str(int(time.time()) + 60),
            }

        # Ensure requests_per_minute is a valid non-negative integer
        # Note: 0 is a valid limit (no requests allowed), only None means unlimited
        # This validation will catch any type issues early
        if not isinstance(requests_per_minute, int):
            raise ValueError(
                f"requests_per_minute must be an integer, got {type(requests_per_minute)} "
                f"(value: {requests_per_minute}, repr: {repr(requests_per_minute)})"
            )
        if requests_per_minute < 0:
            raise ValueError(f"requests_per_minute must be non-negative, got {requests_per_minute}")

        # If remaining and reset_time not provided, calculate them (without incrementing)
        if remaining is None or reset_time is None:
            remaining, reset_time = await self._get_current_rate_limit_status(
                tier_name, identifier, requests_per_minute
            )

        # Return headers with the provided or calculated values
        # Convert to string explicitly to ensure correct type
        return {
            "X-RateLimit-Limit": str(requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

    async def _get_current_rate_limit_status(
        self, tier_name: str, identifier: str, requests_per_minute: int
    ) -> Tuple[int, int]:
        """
        Get current rate limit status without incrementing.

        Returns:
            Tuple of (remaining: int, reset_time: int)
        """
        if self._redis_client is None:
            return requests_per_minute, int(time.time()) + 60

        try:
            redis_key = f"rate_limit:{tier_name}:{identifier}"
            current_minute = int(time.time() // 60)
            window_key = f"{redis_key}:{current_minute}"

            # Get current count without incrementing
            count = await self._redis_client.get(window_key)
            current_count = int(count) if count else 0

            remaining = max(0, requests_per_minute - current_count)
            reset_time = (current_minute + 1) * 60

            return remaining, reset_time

        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            return requests_per_minute, int(time.time()) + 60
