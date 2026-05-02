import asyncio
import base64
import hashlib
import inspect
import json
import logging
import os
import time
from functools import wraps
from typing import Any, Iterable, Optional
from urllib.parse import parse_qsl, urlencode

import redis.asyncio as redis
from dotenv import load_dotenv
from starlette.datastructures import Headers
from starlette.responses import Response

from app.security_utils import stable_hex_digest
from app.services.durable_response_cache import (
    delete_all_durable_api_responses,
    delete_durable_api_response,
    delete_durable_api_responses_for_tags,
    delete_durable_api_responses_with_prefix,
    get_durable_api_response,
    store_durable_api_response,
)

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Get Redis connection parameters from environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Get caching environment variable
ENDPOINT_CACHE = os.getenv("ENDPOINT_CACHE", "false").lower() == "true"
CACHE_DEBUG_HEADERS = os.getenv("CACHE_DEBUG_HEADERS", "false").lower() == "true"
CACHE_LOG_EVENTS = os.getenv("CACHE_LOG_EVENTS", "false").lower() == "true"

# Default cache expiration (12 hours)
DEFAULT_CACHE_TTL = int(os.getenv("CACHE_TTL", 43200))

# Cache key namespace/versioning
CACHE_VERSION = os.getenv("CACHE_VERSION", "v2").strip() or "v2"
CACHE_APP_VERSION = os.getenv("CACHE_APP_VERSION", "").strip()
CACHE_ROOT = f"cache:{CACHE_VERSION}" + (f":{CACHE_APP_VERSION}" if CACHE_APP_VERSION else "")

# Default timeouts / safety rails
REDIS_TIMEOUT_SECONDS = float(os.getenv("REDIS_TIMEOUT_SECONDS", "0.5"))
REDIS_LOCK_TTL_SECONDS = int(os.getenv("REDIS_LOCK_TTL_SECONDS", "10"))
CACHE_LOCK_WAIT_SECONDS = float(os.getenv("CACHE_LOCK_WAIT_SECONDS", "0.25"))
STALE_IF_ERROR_SECONDS = int(os.getenv("STALE_IF_ERROR_SECONDS", "300"))
MAX_STALE_EXTENSION_SECONDS = int(os.getenv("MAX_STALE_EXTENSION_SECONDS", "3600"))
TAG_INDEX_TTL_PADDING_SECONDS = int(os.getenv("TAG_INDEX_TTL_PADDING_SECONDS", "60"))

# Response caching record format
RECORD_SCHEMA_VERSION = 2


def _now_epoch() -> float:
    return time.time()


def _b64encode(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64decode(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _weak_etag_from_body(body: bytes) -> str:
    # Weak ETag is safe across transport-level transforms (e.g., gzip).
    digest = hashlib.sha256(body).hexdigest()
    return f'W/"{digest}"'


def weak_etag_from_body(body: bytes) -> str:
    """Public helper for computing weak ETags from response bytes."""
    return _weak_etag_from_body(body)


def cache_control_header(*, ttl_seconds: int) -> str:
    """Shared Cache-Control policy for cached responses.

    Browsers revalidate (max-age=0) while shared caches can store and serve stale
    while revalidating / on error.
    """
    hard_ttl = int(os.getenv("CACHE_HARD_TTL_SECONDS", str(int(ttl_seconds) * 2)))
    swr = max(0, hard_ttl - int(ttl_seconds))
    sie = max(0, int(STALE_IF_ERROR_SECONDS))
    return (
        f"public, max-age=0, s-maxage={int(ttl_seconds)}, "
        f"stale-while-revalidate={int(swr)}, stale-if-error={int(sie)}"
    )


def immutable_asset_cache_control_header() -> str:
    """Cache-Control policy for content-addressed immutable assets."""
    max_age = int(os.getenv("IMMUTABLE_ASSET_MAX_AGE_SECONDS", "31536000"))
    return f"public, max-age={max_age}, immutable"


def alias_redirect_cache_control_header() -> str:
    """Cache-Control policy for resource-id to immutable-asset redirects."""
    browser_ttl = int(os.getenv("ALIAS_REDIRECT_BROWSER_TTL_SECONDS", "3600"))
    shared_ttl = int(os.getenv("ALIAS_REDIRECT_SHARED_TTL_SECONDS", "86400"))
    swr = int(os.getenv("ALIAS_REDIRECT_STALE_WHILE_REVALIDATE_SECONDS", "604800"))
    return f"public, max-age={browser_ttl}, s-maxage={shared_ttl}, stale-while-revalidate={swr}"


def _log_cache_event(event: str, **fields: Any) -> None:
    """Optional structured-ish cache event logging for observability."""
    if not CACHE_LOG_EVENTS:
        return
    try:
        payload = {"event": event, **fields}
        logger.info("cache_event %s", json.dumps(payload, separators=(",", ":"), sort_keys=True))
    except Exception:
        logger.info("cache_event %s %s", event, fields)


def _normalize_query_string(qs: str) -> str:
    """Normalize a query string for deterministic cache keys.

    Preserves duplicates and bracket-notation params.
    """
    if not qs:
        return ""
    pairs = parse_qsl(qs, keep_blank_values=True)
    pairs.sort(key=lambda kv: (kv[0], kv[1]))
    return urlencode(pairs, doseq=True)


def build_cache_key(
    *,
    request: Any,
    namespace: str,
    params: dict[str, Any],
    vary_headers: Iterable[str] = ("accept", "accept-encoding"),
) -> str:
    """Central cache key builder.

    Includes method/path/query + select headers in addition to handler params.
    """
    method = getattr(request, "method", "") or ""

    try:
        path = request.url.path  # type: ignore[attr-defined]
    except Exception:
        path = ""

    raw_qs = ""
    try:
        raw_bytes = request.scope.get("query_string", b"")  # type: ignore[attr-defined]
        if isinstance(raw_bytes, (bytes, bytearray)):
            raw_qs = raw_bytes.decode("utf-8")
        else:
            raw_qs = str(raw_bytes)
    except Exception:
        raw_qs = ""

    normalized_qs = _normalize_query_string(raw_qs)

    vary: dict[str, str] = {}
    try:
        for h in vary_headers:
            hv = request.headers.get(h)  # type: ignore[attr-defined]
            if hv:
                vary[h.lower()] = hv
    except Exception:
        pass

    key_material = {
        "method": method.upper(),
        "path": path,
        "query": normalized_qs,
        "vary": vary,
        "params": params,
    }
    return CacheService.generate_cache_key(namespace, **key_material)


def _filter_cacheable_headers(headers: Headers | dict[str, str]) -> dict[str, str]:
    # Keep only headers that are meaningful to clients and stable across requests.
    # Exclude hop-by-hop and runtime-generated headers.
    if isinstance(headers, Headers):
        hdrs = dict(headers)
    else:
        hdrs = dict(headers)

    deny = {
        "content-length",
        "content-encoding",
        "date",
        "server",
        "connection",
        "keep-alive",
        "transfer-encoding",
        # Per-request diagnostics should describe the live request, not a cached one.
        "server-timing",
        "x-search-semantic-cache",
    }
    allowed = {}
    for k, v in hdrs.items():
        lk = k.lower()
        if lk in deny:
            continue
        allowed[lk] = v
    return allowed


def _resource_cache_tags_from_body(body: bytes) -> set[str]:
    """Extract resource tags from JSON:API response bodies for targeted invalidation."""
    try:
        payload = json.loads(body)
    except Exception:
        return set()

    if not isinstance(payload, dict):
        return set()

    data = payload.get("data")
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return set()

    tags: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        resource_id = item.get("id")
        if not resource_id:
            attributes = item.get("attributes")
            if isinstance(attributes, dict):
                resource_id = attributes.get("id")
        if resource_id:
            tags.add(f"resource:{resource_id}")
    return tags


def _response_cache_tags(
    *,
    namespace: str,
    tags: Optional[Iterable[str]],
    cache_args: dict[str, Any],
    path: str,
    body: bytes,
) -> set[str]:
    """Return durable/Redis tags for a cached endpoint response."""
    tag_set: set[str] = set(tags or [])
    tag_set.add(f"ns:{namespace}")

    # Heuristics for common public APIs.
    if namespace.endswith(".search"):
        tag_set.add("search")
    if namespace.endswith(".suggest"):
        tag_set.add("suggest")
    if "/resources" in path:
        tag_set.add("resource")
    if "gazetteer" in namespace or "/gazetteer" in path:
        tag_set.add("gazetteer")
    if "facet_name" in cache_args and cache_args.get("facet_name"):
        tag_set.add(f"facet:{cache_args.get('facet_name')}")
        tag_set.add("search")
    if "/search" in path or "/resources" in path:
        tag_set.update(_resource_cache_tags_from_body(body))

    # Resource-like endpoints commonly use 'id'.
    rid = cache_args.get("id") or cache_args.get("resource_id")
    if rid and "/resources/" in path:
        tag_set.add(f"resource:{rid}")
    return tag_set


def _warm_metadata_from_request(request: Any) -> Optional[dict[str, str]]:
    """Return enough request metadata to replay a cached public GET."""
    if request is None:
        return None
    method = (getattr(request, "method", "") or "").upper()
    if method and method != "GET":
        return None
    try:
        path = str(request.url.path)
    except Exception:
        return None
    if not path:
        return None
    try:
        query = str(request.url.query or "")
    except Exception:
        query = ""
    return {"method": "GET", "path": path, "query": query}


def _find_request_in_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    request = kwargs.get("request")
    if request is not None:
        return request
    for arg in args:
        if hasattr(arg, "url") and hasattr(arg, "method"):
            return arg
    return None


async def _redis_call(coro):
    """Bounded wait for Redis operations; raises on timeout/errors."""
    return await asyncio.wait_for(coro, timeout=REDIS_TIMEOUT_SECONDS)


class CacheService:
    """Service to handle Redis caching operations."""

    _instance = None
    _redis_client = None

    def __new__(cls):
        """Singleton pattern to avoid multiple Redis connections."""
        if cls._instance is None:
            cls._instance = super(CacheService, cls).__new__(cls)
            cls._instance._init_redis_client()
        return cls._instance

    def _init_redis_client(self):
        """Initialize Redis client."""
        try:
            if ENDPOINT_CACHE:
                logger.info(f"Initializing Redis client on {REDIS_HOST}:{REDIS_PORT}")
                self._redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=False,  # We'll handle serialization/deserialization ourselves
                    socket_timeout=REDIS_TIMEOUT_SECONDS,
                    socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
                )
                logger.info("Redis client initialized successfully")
            else:
                logger.info("Endpoint caching is disabled via ENDPOINT_CACHE environment variable")
                self._redis_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {str(e)}")
            self._redis_client = None

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return None

        try:
            data = await _redis_call(self._redis_client.get(key))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving from cache: {str(e)}")
            return None

    async def set(self, key: str, value: Any, ttl: int = DEFAULT_CACHE_TTL) -> bool:
        """Set a JSON-serializable value in cache with expiration."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return False

        try:
            serialized = json.dumps(value)
            return await _redis_call(
                self._redis_client.set(key, serialized.encode("utf-8"), ex=ttl)
            )
        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")
            return False

    async def get_many(self, keys: Iterable[str]) -> dict[str, Any]:
        """Get many JSON-serializable cache values in one Redis round trip."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return {}

        key_list = [str(key) for key in keys if key]
        if not key_list:
            return {}

        try:
            values = await _redis_call(self._redis_client.mget(key_list))
            results: dict[str, Any] = {}
            for key, raw in zip(key_list, values):
                if not raw:
                    continue
                results[key] = json.loads(raw)
            return results
        except Exception as e:
            logger.error(f"Error retrieving many from cache: {str(e)}")
            return {}

    async def set_many(self, values: dict[str, Any], ttl: int = DEFAULT_CACHE_TTL) -> bool:
        """Set many JSON-serializable cache values with the same expiration."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return False

        if not values:
            return True

        try:
            pipe = self._redis_client.pipeline(transaction=False)
            for key, value in values.items():
                serialized = json.dumps(value).encode("utf-8")
                pipe.set(str(key), serialized, ex=ttl)
            await _redis_call(pipe.execute())
            return True
        except Exception as e:
            logger.error(f"Error setting many cache values: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if not ENDPOINT_CACHE:
            return False

        durable_deleted = await delete_durable_api_response(key)
        try:
            if not self._redis_client:
                return durable_deleted
            return bool(await _redis_call(self._redis_client.delete(key))) or durable_deleted
        except Exception as e:
            logger.error(f"Error deleting from cache: {str(e)}")
            return durable_deleted

    async def flush_all(self) -> bool:
        """Flush all cache entries."""
        if not ENDPOINT_CACHE:
            return False

        durable_deleted = await delete_all_durable_api_responses()
        try:
            if not self._redis_client:
                return durable_deleted >= 0
            return bool(await _redis_call(self._redis_client.flushdb()))
        except Exception as e:
            logger.error(f"Error flushing cache: {str(e)}")
            return durable_deleted >= 0

    async def get_record(self, key: str) -> Optional[dict[str, Any]]:
        """Get a cached response record (v2+)."""
        if not ENDPOINT_CACHE:
            return None

        if self._redis_client:
            try:
                raw = await _redis_call(self._redis_client.get(key))
                if raw:
                    record = json.loads(raw)
                    if isinstance(record, dict) and record.get("schema") == RECORD_SCHEMA_VERSION:
                        return record
            except Exception as e:
                logger.error(f"Error retrieving record from cache: {str(e)}")

        durable = await get_durable_api_response(key)
        if not durable:
            return None

        record, tags, namespace = durable
        if record.get("schema") != RECORD_SCHEMA_VERSION:
            return None

        now = _now_epoch()
        hard_exp = float(record.get("hard_exp") or 0)
        redis_ttl = max(1, int(hard_exp - now)) if hard_exp else DEFAULT_CACHE_TTL
        await self.set_record(
            key,
            record,
            ttl_seconds=redis_ttl,
            write_durable=False,
        )
        if tags:
            await self.tag_cache_key(key, tags, ttl_seconds=redis_ttl)
        _log_cache_event("durable_hit", namespace=namespace or "", redis_ttl=redis_ttl)
        return record

    async def set_record(
        self,
        key: str,
        record: dict[str, Any],
        ttl_seconds: int,
        *,
        namespace: str | None = None,
        tags: Iterable[str] | None = None,
        write_durable: bool = True,
    ) -> bool:
        """Set a cached response record (v2+) with expiration."""
        if not ENDPOINT_CACHE:
            return False
        redis_ok = False
        try:
            if self._redis_client:
                raw = json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")
                redis_ok = bool(await _redis_call(self._redis_client.set(key, raw, ex=ttl_seconds)))
        except Exception as e:
            logger.error(f"Error setting record cache: {str(e)}")
        durable_ok = False
        if write_durable and namespace:
            durable_ok = await store_durable_api_response(
                key,
                record,
                namespace=namespace,
                tags=tags or [],
            )
        return redis_ok or durable_ok

    async def acquire_lock(self, lock_key: str) -> bool:
        """Acquire a per-key lock to prevent stampedes."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return False

        try:
            # Value doesn't matter; we just need NX with expiry.
            ok = await _redis_call(
                self._redis_client.set(lock_key, b"1", nx=True, ex=REDIS_LOCK_TTL_SECONDS)
            )
            return bool(ok)
        except Exception:
            return False

    @staticmethod
    def _tagset_key(tag: str) -> str:
        safe = str(tag).replace(" ", "_")
        return f"{CACHE_ROOT}:tag:{safe}"

    @staticmethod
    def _keytags_key(cache_key: str) -> str:
        digest = stable_hex_digest(cache_key, digest_size=16)
        return f"{CACHE_ROOT}:keytags:{digest}"

    async def tag_cache_key(self, cache_key: str, tags: Iterable[str], ttl_seconds: int) -> None:
        """Index cache_key under one or more tags (and store reverse mapping)."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return
        tag_list = [t for t in {str(t) for t in tags} if t]
        if not tag_list:
            return
        try:
            pipe = self._redis_client.pipeline(transaction=False)
            keytags_key = self._keytags_key(cache_key)
            for tag in tag_list:
                tkey = self._tagset_key(tag)
                pipe.sadd(tkey, cache_key.encode("utf-8"))
                # Expire tag sets around the same time as the cached object.
                pipe.expire(tkey, int(ttl_seconds) + TAG_INDEX_TTL_PADDING_SECONDS)
                pipe.sadd(keytags_key, tag.encode("utf-8"))
            pipe.expire(keytags_key, int(ttl_seconds) + TAG_INDEX_TTL_PADDING_SECONDS)
            await _redis_call(pipe.execute())
        except Exception as e:
            logger.error(f"Error tagging cache key: {e}")

    async def invalidate_tags(self, tags: Iterable[str]) -> int:
        """Invalidate all cached keys associated with the given tags.

        Returns number of cached response keys deleted (best-effort).
        """
        if not ENDPOINT_CACHE:
            return 0
        tag_values = {str(t) for t in tags if t}
        durable_deleted = await delete_durable_api_responses_for_tags(tag_values)
        deleted = 0
        if not self._redis_client:
            return durable_deleted
        try:
            for tag in tag_values:
                tagset_key = self._tagset_key(tag)
                members = await _redis_call(self._redis_client.smembers(tagset_key))
                if not members:
                    continue
                for raw_key in members:
                    cache_key = (
                        raw_key.decode("utf-8")
                        if isinstance(raw_key, (bytes, bytearray))
                        else str(raw_key)
                    )
                    keytags_key = self._keytags_key(cache_key)
                    other_tags = await _redis_call(self._redis_client.smembers(keytags_key))
                    if other_tags:
                        pipe = self._redis_client.pipeline(transaction=False)
                        for ot in other_tags:
                            otag = (
                                ot.decode("utf-8")
                                if isinstance(ot, (bytes, bytearray))
                                else str(ot)
                            )
                            pipe.srem(self._tagset_key(otag), cache_key.encode("utf-8"))
                        pipe.delete(keytags_key)
                        pipe.delete(cache_key)
                        await _redis_call(pipe.execute())
                    else:
                        # If reverse mapping is missing, still delete the cache key.
                        await _redis_call(self._redis_client.delete(cache_key))
                    deleted += 1
                # Finally delete the tag set itself.
                await _redis_call(self._redis_client.delete(tagset_key))
        except Exception as e:
            logger.error(f"Error invalidating tags {list(tags)}: {e}")
        return deleted + durable_deleted

    async def cached_records_for_tags(self, tags: Iterable[str]) -> list[dict[str, Any]]:
        """Return cached response records associated with tags, before invalidation."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return []

        records_by_key: dict[str, dict[str, Any]] = {}
        try:
            for tag in {str(t) for t in tags if t}:
                members = await _redis_call(self._redis_client.smembers(self._tagset_key(tag)))
                for raw_key in members or []:
                    cache_key = (
                        raw_key.decode("utf-8")
                        if isinstance(raw_key, (bytes, bytearray))
                        else str(raw_key)
                    )
                    if cache_key in records_by_key:
                        continue
                    record = await self.get_record(cache_key)
                    if record:
                        records_by_key[cache_key] = {"cache_key": cache_key, **record}
        except Exception as e:
            logger.error(f"Error collecting cached records for tags {list(tags)}: {e}")
        return list(records_by_key.values())

    @staticmethod
    def generate_cache_key(namespace: str, *args, **kwargs) -> str:
        """Generate a deterministic, versioned cache key from arguments.

        Keys are structured to support prefix invalidation:
          {CACHE_ROOT}:{namespace}:{digest(args/kwargs)}
        """
        safe_namespace = str(namespace).replace(" ", "_")
        key_parts = [safe_namespace]

        # Add positional args
        for arg in args:
            if isinstance(arg, (str, int, float, bool, type(None))):
                key_parts.append(str(arg))
            else:
                # Handle FastAPI Query objects and other non-serializable types
                try:
                    key_parts.append(json.dumps(arg, sort_keys=True))
                except (TypeError, ValueError):
                    # For non-serializable objects, use their string representation
                    key_parts.append(str(arg))

        # Add keyword args (sorted for consistency)
        for k in sorted(kwargs.keys()):
            v = kwargs[k]
            if isinstance(v, (str, int, float, bool, type(None))):
                key_parts.append(f"{k}={v}")
            else:
                # Handle FastAPI Query objects and other non-serializable types
                try:
                    key_parts.append(f"{k}={json.dumps(v, sort_keys=True)}")
                except (TypeError, ValueError):
                    # For non-serializable objects, use their string representation
                    key_parts.append(f"{k}={str(v)}")

        # Join all parts and hash them
        key_string = ":".join(key_parts)
        digest = stable_hex_digest(key_string, digest_size=16)
        return f"{CACHE_ROOT}:{safe_namespace}:{digest}"


# Create decorator for caching endpoint responses
def cached_endpoint(ttl: int = DEFAULT_CACHE_TTL, *, tags: Optional[Iterable[str]] = None):
    """Decorator to cache endpoint responses (binary-safe, versioned keys)."""

    def decorator(func):
        def _cache_control_header(*, ttl_seconds: int) -> str:
            return cache_control_header(ttl_seconds=ttl_seconds)

        async def _refresh_in_background(
            *,
            cache_service: CacheService,
            cache_key: str,
            key_namespace: str,
            args: tuple[Any, ...],
            kwargs: dict[str, Any],
            ttl_seconds: int,
            cache_args: dict[str, Any],
            explicit_tags: Optional[Iterable[str]],
            path: str,
        ) -> None:
            """Recompute and refresh a cached key. Best-effort; never raises."""
            try:
                result = await func(*args, **kwargs)
                if isinstance(result, Response) and getattr(result, "body", None) is not None:
                    if result.status_code == 200:
                        body: bytes = (
                            result.body
                            if isinstance(result.body, (bytes, bytearray))
                            else bytes(result.body)
                        )
                        etag = _weak_etag_from_body(body)
                        headers = _filter_cacheable_headers(result.headers)

                        now = _now_epoch()
                        soft_exp = now + float(ttl_seconds)
                        hard_ttl = int(
                            os.getenv("CACHE_HARD_TTL_SECONDS", str(int(ttl_seconds) * 2))
                        )
                        hard_exp = now + float(hard_ttl)
                        redis_ttl = max(1, int(hard_exp - now))

                        record = {
                            "schema": RECORD_SCHEMA_VERSION,
                            "created": now,
                            "soft_exp": soft_exp,
                            "hard_exp": hard_exp,
                            "status": int(result.status_code),
                            "headers": headers,
                            "etag": etag,
                            "body_b64": _b64encode(body),
                        }
                        warm = _warm_metadata_from_request(_find_request_in_call(args, kwargs))
                        if warm:
                            record["warm"] = warm
                        tag_set = _response_cache_tags(
                            namespace=key_namespace,
                            tags=explicit_tags,
                            cache_args=cache_args,
                            path=path,
                            body=body,
                        )
                        await cache_service.set_record(
                            cache_key,
                            record,
                            ttl_seconds=redis_ttl,
                            namespace=key_namespace,
                            tags=tag_set,
                        )
                        await cache_service.tag_cache_key(
                            cache_key,
                            tag_set,
                            ttl_seconds=redis_ttl,
                        )
                        _log_cache_event(
                            "refresh_store", namespace=key_namespace, redis_ttl=redis_ttl
                        )
            except Exception as e:
                # Extend stale window on failure (stale-if-error) so we can keep serving
                # a previously cached value during upstream outages.
                try:
                    record = await cache_service.get_record(cache_key)
                    if record:
                        now = _now_epoch()
                        hard_exp = float(record.get("hard_exp", 0))
                        # Extend hard expiry, but cap extension.
                        max_hard = now + float(MAX_STALE_EXTENSION_SECONDS)
                        new_hard = min(max_hard, max(hard_exp, now) + float(STALE_IF_ERROR_SECONDS))
                        if new_hard > hard_exp:
                            record["hard_exp"] = new_hard
                            # Keep TTL aligned with new hard expiry.
                            redis_ttl = max(1, int(new_hard - now))
                            await cache_service.set_record(
                                cache_key,
                                record,
                                ttl_seconds=redis_ttl,
                                write_durable=False,
                            )
                except Exception:
                    pass
                logger.warning(f"Cache refresh failed for {key_namespace}: {e}")
                _log_cache_event("refresh_fail", namespace=key_namespace, error=str(e))

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not ENDPOINT_CACHE:
                return await func(*args, **kwargs)

            # Get the function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Pull request if present (we don't include it directly in args hashing)
            request = bound_args.arguments.get("request")
            # Fallback: Starlette passes request as first positional when handler has *args
            if request is None and args:
                request = args[0]
            cache_args = {k: v for k, v in bound_args.arguments.items() if k != "request"}

            namespace = f"{func.__module__}.{func.__name__}"
            cache_key = (
                build_cache_key(request=request, namespace=namespace, params=cache_args)
                if request is not None
                else CacheService.generate_cache_key(namespace, **cache_args)
            )
            path = ""
            try:
                path = request.url.path if request else ""
            except Exception:
                path = ""

            # Try to get from cache
            cache_service = CacheService()
            record = await cache_service.get_record(cache_key)

            if record is not None:
                now = _now_epoch()
                soft_exp = float(record.get("soft_exp", 0))
                hard_exp = float(record.get("hard_exp", 0))
                # If Redis TTL hasn't expired but record says hard-expired, treat as miss.
                if hard_exp and now > hard_exp:
                    record = None
                else:
                    is_stale = bool(soft_exp and now > soft_exp)
                    cache_state = "stale" if is_stale else "hit"
                    logger.debug(f"Cache {cache_state} for {cache_key}")
                    # Approximate bytes: base64 expands by ~4/3; keep it simple for logs.
                    _log_cache_event(
                        cache_state,
                        namespace=namespace,
                        status=int(record.get("status", 200)),
                        approx_bytes=int(len(record.get("body_b64", "")) * 0.75),
                    )

                    # Stale-while-revalidate: serve stale, refresh in background.
                    if is_stale:
                        lock_key = f"{cache_key}:lock"
                        if await cache_service.acquire_lock(lock_key):
                            _log_cache_event("refresh_start", namespace=namespace)
                            asyncio.create_task(
                                _refresh_in_background(
                                    cache_service=cache_service,
                                    cache_key=cache_key,
                                    key_namespace=namespace,
                                    args=args,
                                    kwargs=kwargs,
                                    ttl_seconds=ttl,
                                    cache_args=cache_args,
                                    explicit_tags=tags,
                                    path=path,
                                )
                            )

                    body = _b64decode(record["body_b64"])
                    headers = record.get("headers", {}) or {}
                    status_code = int(record.get("status", 200))

                    etag = record.get("etag")
                    # Conditional request support (304)
                    if request is not None and etag:
                        inm = request.headers.get("if-none-match")
                        if inm and inm == etag:
                            resp = Response(status_code=304)
                            resp.headers["ETag"] = etag
                            resp.headers["Cache-Control"] = _cache_control_header(ttl_seconds=ttl)
                            # gzip middleware may be enabled; Accept affects representation too.
                            resp.headers["Vary"] = "Accept-Encoding, Accept"
                            if CACHE_DEBUG_HEADERS:
                                resp.headers["X-Cache"] = cache_state.upper()
                            return resp

                    resp = Response(content=body, status_code=status_code)
                    for hk, hv in headers.items():
                        resp.headers[hk] = hv
                    if etag:
                        resp.headers["ETag"] = etag
                    resp.headers["Cache-Control"] = _cache_control_header(ttl_seconds=ttl)
                    resp.headers["Vary"] = "Accept-Encoding, Accept"
                    if CACHE_DEBUG_HEADERS:
                        resp.headers["X-Cache"] = cache_state.upper()
                    return resp

            # Cache miss, execute the function
            logger.debug(f"Cache miss for {cache_key}")
            try:
                # Prevent stampede on misses: only one request recomputes if possible.
                lock_key = f"{cache_key}:lock"
                have_lock = await cache_service.acquire_lock(lock_key)
                if not have_lock:
                    _log_cache_event("miss_lock_wait", namespace=namespace)
                    # Wait briefly for another worker to populate the cache.
                    deadline = _now_epoch() + CACHE_LOCK_WAIT_SECONDS
                    while _now_epoch() < deadline:
                        await asyncio.sleep(0.05)
                        record = await cache_service.get_record(cache_key)
                        if record:
                            body = _b64decode(record["body_b64"])
                            headers = record.get("headers", {}) or {}
                            status_code = int(record.get("status", 200))
                            etag = record.get("etag")
                            resp = Response(content=body, status_code=status_code)
                            for hk, hv in headers.items():
                                resp.headers[hk] = hv
                            if etag:
                                resp.headers["ETag"] = etag
                            resp.headers["Cache-Control"] = _cache_control_header(ttl_seconds=ttl)
                            resp.headers["Vary"] = "Accept-Encoding, Accept"
                            if CACHE_DEBUG_HEADERS:
                                resp.headers["X-Cache"] = "WAIT_HIT"
                            _log_cache_event("wait_hit", namespace=namespace)
                            return resp

                start = _now_epoch()
                result = await func(*args, **kwargs)
                _log_cache_event(
                    "recompute_done", namespace=namespace, ms=int((_now_epoch() - start) * 1000)
                )

                # Only cache successful, non-streaming responses.
                if isinstance(result, Response) and getattr(result, "body", None) is not None:
                    if result.status_code == 200:
                        body: bytes = (
                            result.body
                            if isinstance(result.body, (bytes, bytearray))
                            else bytes(result.body)
                        )
                        etag = _weak_etag_from_body(body)
                        headers = _filter_cacheable_headers(result.headers)

                        now = _now_epoch()
                        soft_exp = now + float(ttl)
                        hard_ttl = int(os.getenv("CACHE_HARD_TTL_SECONDS", str(int(ttl) * 2)))
                        hard_exp = now + float(hard_ttl)
                        redis_ttl = max(1, int(hard_exp - now))

                        record = {
                            "schema": RECORD_SCHEMA_VERSION,
                            "created": now,
                            "soft_exp": soft_exp,
                            "hard_exp": hard_exp,
                            "status": int(result.status_code),
                            "headers": headers,
                            "etag": etag,
                            "body_b64": _b64encode(body),
                        }
                        warm = _warm_metadata_from_request(request)
                        if warm:
                            record["warm"] = warm
                        tag_set = _response_cache_tags(
                            namespace=namespace,
                            tags=tags,
                            cache_args=cache_args,
                            path=path,
                            body=body,
                        )
                        await cache_service.set_record(
                            cache_key,
                            record,
                            ttl_seconds=redis_ttl,
                            namespace=namespace,
                            tags=tag_set,
                        )
                        await cache_service.tag_cache_key(cache_key, tag_set, ttl_seconds=redis_ttl)
                        _log_cache_event(
                            "store",
                            namespace=namespace,
                            redis_ttl=redis_ttl,
                            tags=sorted(tag_set),
                        )

                        # Add HTTP validators/semantics to the live response too.
                        result.headers["ETag"] = etag
                        result.headers["Cache-Control"] = _cache_control_header(ttl_seconds=ttl)
                        result.headers["Vary"] = "Accept-Encoding, Accept"
                        if CACHE_DEBUG_HEADERS:
                            result.headers["X-Cache"] = "MISS"
                return result
            except Exception:
                # Don't cache errors, just re-raise them
                raise

        return wrapper

    return decorator


# Create a function to invalidate cache with a prefix pattern
async def invalidate_cache_with_prefix(prefix: str) -> bool:
    """Invalidate all cache keys starting with a specific prefix."""
    if not ENDPOINT_CACHE:
        return True

    try:
        cache_service = CacheService()

        # v2+ keys: {CACHE_ROOT}:{namespace}:{md5}
        pattern = f"{CACHE_ROOT}:{prefix}*"
        await delete_durable_api_responses_with_prefix(pattern.rstrip("*"))
        if not cache_service._redis_client:
            return True

        deleted = 0
        async for key in cache_service._redis_client.scan_iter(match=pattern, count=500):
            deleted += int(await _redis_call(cache_service._redis_client.delete(key)))
        return True
    except Exception as e:
        logger.error(f"Error invalidating cache with prefix {prefix}: {str(e)}")
        return False
