from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

import redis

logger = logging.getLogger(__name__)

_LOCAL_STATE_LOCK = threading.Lock()
_LOCAL_NEXT_ALLOWED: dict[str, float] = {}
_LOCAL_SLOT_LOCKS: dict[str, list[threading.Lock]] = {}

_redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    db=0,
    decode_responses=True,
)

_RELEASE_IF_OWNER = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


@dataclass(frozen=True)
class ProviderThrottleProfile:
    per_origin_concurrency: int
    min_delay_seconds: float
    lock_ttl_seconds: int
    poll_interval_seconds: float


@dataclass(frozen=True)
class ProviderLease:
    origin: str
    waited_seconds: float


def normalize_origin(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _parse_overrides() -> dict[str, dict[str, float | int]]:
    raw = os.getenv("THUMBNAIL_PROVIDER_OVERRIDES_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid THUMBNAIL_PROVIDER_OVERRIDES_JSON: %s", exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def profile_for_url(url: str | None) -> ProviderThrottleProfile | None:
    origin = normalize_origin(url)
    if not origin:
        return None

    concurrency = max(1, int(os.getenv("THUMBNAIL_PER_ORIGIN_CONCURRENCY", "1")))
    min_delay = max(0.0, float(os.getenv("THUMBNAIL_MIN_DELAY_SECONDS", "1.0")))
    fetch_timeout = int(os.getenv("THUMBNAIL_FETCH_TIMEOUT", "30"))
    lock_ttl = max(fetch_timeout + 30, int(os.getenv("THUMBNAIL_PROVIDER_LOCK_TTL_SECONDS", "90")))
    poll_interval = max(
        0.05,
        float(os.getenv("THUMBNAIL_PROVIDER_POLL_INTERVAL_SECONDS", "0.25")),
    )

    overrides = _parse_overrides()
    override = overrides.get(origin) or overrides.get(urlparse(origin).netloc.lower())
    if isinstance(override, dict):
        concurrency = max(1, int(override.get("per_origin_concurrency", concurrency)))
        min_delay = max(0.0, float(override.get("min_delay_seconds", min_delay)))
        lock_ttl = max(lock_ttl, int(override.get("lock_ttl_seconds", lock_ttl)))

    if concurrency <= 0 and min_delay <= 0:
        return None

    return ProviderThrottleProfile(
        per_origin_concurrency=concurrency,
        min_delay_seconds=min_delay,
        lock_ttl_seconds=lock_ttl,
        poll_interval_seconds=poll_interval,
    )


def _slot_key(origin: str, slot_index: int) -> str:
    return f"thumbnail_provider_slot:{origin}:{slot_index}"


def _pace_lock_key(origin: str) -> str:
    return f"thumbnail_provider_pace_lock:{origin}"


def _next_allowed_key(origin: str) -> str:
    return f"thumbnail_provider_next_allowed:{origin}"


def _local_acquire(origin: str, profile: ProviderThrottleProfile) -> tuple[threading.Lock, float]:
    started = time.time()
    with _LOCAL_STATE_LOCK:
        slot_locks = _LOCAL_SLOT_LOCKS.setdefault(
            origin, [threading.Lock() for _ in range(profile.per_origin_concurrency)]
        )

    acquired_lock: threading.Lock | None = None
    while acquired_lock is None:
        for slot_lock in slot_locks:
            if slot_lock.acquire(blocking=False):
                acquired_lock = slot_lock
                break
        if acquired_lock is None:
            time.sleep(profile.poll_interval_seconds)

    while True:
        with _LOCAL_STATE_LOCK:
            next_allowed = _LOCAL_NEXT_ALLOWED.get(origin, 0.0)
            now = time.time()
            if next_allowed <= now:
                _LOCAL_NEXT_ALLOWED[origin] = now + profile.min_delay_seconds
                break
            wait_for = next_allowed - now
        time.sleep(min(wait_for, profile.poll_interval_seconds))

    return acquired_lock, max(0.0, time.time() - started)


def _local_release(lock: threading.Lock) -> None:
    lock.release()


def _release_redis_key(key: str, owner: str) -> None:
    try:
        _redis_client.eval(_RELEASE_IF_OWNER, 1, key, owner)
    except Exception:
        pass


def _redis_acquire_slot(
    origin: str, profile: ProviderThrottleProfile
) -> tuple[tuple[str, str], float] | None:
    started = time.time()
    while True:
        for slot_index in range(profile.per_origin_concurrency):
            owner = str(uuid.uuid4())
            if _redis_client.set(
                _slot_key(origin, slot_index),
                owner,
                nx=True,
                ex=profile.lock_ttl_seconds,
            ):
                return ((_slot_key(origin, slot_index), owner), max(0.0, time.time() - started))
        time.sleep(profile.poll_interval_seconds)


def _redis_wait_for_pacing(origin: str, profile: ProviderThrottleProfile) -> None:
    if profile.min_delay_seconds <= 0:
        return

    pace_key = _pace_lock_key(origin)
    next_key = _next_allowed_key(origin)

    while True:
        owner = str(uuid.uuid4())
        if not _redis_client.set(pace_key, owner, nx=True, ex=max(5, profile.lock_ttl_seconds)):
            time.sleep(profile.poll_interval_seconds)
            continue

        try:
            raw_next_allowed = _redis_client.get(next_key)
            now = time.time()
            next_allowed = float(raw_next_allowed) if raw_next_allowed else 0.0
            if next_allowed > now:
                wait_for = next_allowed - now
            else:
                wait_for = 0.0
                ttl = max(profile.lock_ttl_seconds, int(profile.min_delay_seconds) + 60)
                _redis_client.set(next_key, now + profile.min_delay_seconds, ex=ttl)
        finally:
            _release_redis_key(pace_key, owner)

        if wait_for <= 0:
            return
        time.sleep(min(wait_for, profile.poll_interval_seconds))


@contextmanager
def provider_request_slot(url: str | None, *, action: str = "thumbnail request"):
    """
    Serialize/police outbound requests per origin.

    This keeps us from hammering one provider with many concurrent requests or tight retries.
    """
    origin = normalize_origin(url)
    profile = profile_for_url(url)
    if not origin or not profile:
        yield ProviderLease(origin=origin or "unknown", waited_seconds=0.0)
        return

    waited_seconds = 0.0
    redis_slot: tuple[str, str] | None = None
    local_slot: threading.Lock | None = None

    try:
        try:
            redis_slot, waited_seconds = _redis_acquire_slot(origin, profile)
            _redis_wait_for_pacing(origin, profile)
        except Exception as exc:
            logger.debug("Redis throttle unavailable for %s: %s", origin, exc)
            local_slot, waited_seconds = _local_acquire(origin, profile)

        if waited_seconds >= profile.poll_interval_seconds:
            logger.info(
                "Provider pacing delayed %s for %s by %.2fs",
                action,
                origin,
                waited_seconds,
            )

        yield ProviderLease(origin=origin, waited_seconds=waited_seconds)
    finally:
        if redis_slot is not None:
            _release_redis_key(redis_slot[0], redis_slot[1])
        if local_slot is not None:
            _local_release(local_slot)
