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

from app.api.v1.utils import JSONResponse

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
    }
    allowed = {}
    for k, v in hdrs.items():
        lk = k.lower()
        if lk in deny:
            continue
        allowed[lk] = v
    return allowed


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
            return await _redis_call(self._redis_client.set(key, serialized.encode("utf-8"), ex=ttl))
        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return False

        try:
            return bool(await _redis_call(self._redis_client.delete(key)))
        except Exception as e:
            logger.error(f"Error deleting from cache: {str(e)}")
            return False

    async def flush_all(self) -> bool:
        """Flush all cache entries."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return False

        try:
            return await _redis_call(self._redis_client.flushdb())
        except Exception as e:
            logger.error(f"Error flushing cache: {str(e)}")
            return False

    async def get_record(self, key: str) -> Optional[dict[str, Any]]:
        """Get a cached response record (v2+)."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return None
        try:
            raw = await _redis_call(self._redis_client.get(key))
            if not raw:
                return None
            record = json.loads(raw)
            if not isinstance(record, dict):
                return None
            if record.get("schema") != RECORD_SCHEMA_VERSION:
                return None
            return record
        except Exception as e:
            logger.error(f"Error retrieving record from cache: {str(e)}")
            return None

    async def set_record(self, key: str, record: dict[str, Any], ttl_seconds: int) -> bool:
        """Set a cached response record (v2+) with expiration."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return False
        try:
            raw = json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")
            return await _redis_call(self._redis_client.set(key, raw, ex=ttl_seconds))
        except Exception as e:
            logger.error(f"Error setting record cache: {str(e)}")
            return False

    async def acquire_lock(self, lock_key: str) -> bool:
        """Acquire a per-key lock to prevent stampedes."""
        if not self._redis_client or not ENDPOINT_CACHE:
            return False

    @staticmethod
    def _tagset_key(tag: str) -> str:
        safe = str(tag).replace(" ", "_")
        return f"{CACHE_ROOT}:tag:{safe}"

    @staticmethod
    def _keytags_key(cache_key: str) -> str:
        digest = hashlib.md5(cache_key.encode()).hexdigest()
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
        if not self._redis_client or not ENDPOINT_CACHE:
            return 0
        deleted = 0
        try:
            for tag in {str(t) for t in tags if t}:
                tagset_key = self._tagset_key(tag)
                members = await _redis_call(self._redis_client.smembers(tagset_key))
                if not members:
                    continue
                for raw_key in members:
                    cache_key = raw_key.decode("utf-8") if isinstance(raw_key, (bytes, bytearray)) else str(raw_key)
                    keytags_key = self._keytags_key(cache_key)
                    other_tags = await _redis_call(self._redis_client.smembers(keytags_key))
                    if other_tags:
                        pipe = self._redis_client.pipeline(transaction=False)
                        for ot in other_tags:
                            otag = ot.decode("utf-8") if isinstance(ot, (bytes, bytearray)) else str(ot)
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
        return deleted
        try:
            # Value doesn't matter; we just need NX with expiry.
            ok = await _redis_call(
                self._redis_client.set(lock_key, b"1", nx=True, ex=REDIS_LOCK_TTL_SECONDS)
            )
            return bool(ok)
        except Exception:
            return False

    @staticmethod
    def generate_cache_key(namespace: str, *args, **kwargs) -> str:
        """Generate a deterministic, versioned cache key from arguments.

        Keys are structured to support prefix invalidation:
          {CACHE_ROOT}:{namespace}:{md5(args/kwargs)}
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
        digest = hashlib.md5(key_string.encode()).hexdigest()
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
                        hard_ttl = int(os.getenv("CACHE_HARD_TTL_SECONDS", str(int(ttl_seconds) * 2)))
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
                        await cache_service.set_record(cache_key, record, ttl_seconds=redis_ttl)
                        _log_cache_event("refresh_store", namespace=key_namespace, redis_ttl=redis_ttl)
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
                            await cache_service.set_record(cache_key, record, ttl_seconds=redis_ttl)
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
            cache_args = {k: v for k, v in bound_args.arguments.items() if k != "request"}

            namespace = f"{func.__module__}.{func.__name__}"
            cache_key = (
                build_cache_key(request=request, namespace=namespace, params=cache_args)
                if request is not None
                else CacheService.generate_cache_key(namespace, **cache_args)
            )

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
                _log_cache_event("recompute_done", namespace=namespace, ms=int((_now_epoch() - start) * 1000))

                # Only cache successful, non-streaming responses.
                if isinstance(result, Response) and getattr(result, "body", None) is not None:
                    if result.status_code == 200:
                        body: bytes = result.body if isinstance(result.body, (bytes, bytearray)) else bytes(result.body)
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
                        await cache_service.set_record(cache_key, record, ttl_seconds=redis_ttl)
                        # Tagging for invalidation
                        tag_set: set[str] = set(tags or [])
                        tag_set.add(f"ns:{namespace}")
                        # Heuristics for common public APIs
                        if namespace.endswith(".search"):
                            tag_set.add("search")
                        if namespace.endswith(".suggest"):
                            tag_set.add("suggest")
                        path = ""
                        try:
                            path = request.url.path if request else ""
                        except Exception:
                            path = ""
                        if "/resources" in path:
                            tag_set.add("resource")
                        if "gazetteer" in namespace or "/gazetteer" in path:
                            tag_set.add("gazetteer")
                        if "facet_name" in cache_args and cache_args.get("facet_name"):
                            tag_set.add(f"facet:{cache_args.get('facet_name')}")
                            tag_set.add("search")
                        # Resource-like endpoints commonly use 'id'
                        rid = cache_args.get("id") or cache_args.get("resource_id")
                        if rid and "/resources/" in path:
                            tag_set.add(f"resource:{rid}")
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
        if not cache_service._redis_client:
            return False

        # v2+ keys: {CACHE_ROOT}:{namespace}:{md5}
        pattern = f"{CACHE_ROOT}:{prefix}*"
        deleted = 0
        async for key in cache_service._redis_client.scan_iter(match=pattern, count=500):
            deleted += int(await _redis_call(cache_service._redis_client.delete(key)))
        return True
    except Exception as e:
        logger.error(f"Error invalidating cache with prefix {prefix}: {str(e)}")
        return False
