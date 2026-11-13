"""Versioned, term-centric catalog search. No natural-language rewriting is performed."""

import copy
import logging
import os
import re
import time
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps

from fastapi import HTTPException

from app.services.cache_service import CacheService

from .relevance_fields import SEARCH_FIELD_WEIGHTS

logger = logging.getLogger(__name__)

# This memo lives for one request only. Never retain alias/revision state across
# requests: writes and alias cutovers must invalidate even warm response caches.
_request_generations: ContextVar[dict | None] = ContextVar("search_generations", default=None)
_matching_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
MATCHING_CACHE_TTL = 60
MATCHING_CACHE_SIZE = 4096


def clear_matching_cache() -> None:
    """Clear process-local decisions (useful for cold-stage benchmarks)."""
    _matching_cache.clear()


def _remember_matching(key: str, mode: str) -> None:
    _matching_cache[key] = (time.monotonic() + MATCHING_CACHE_TTL, mode)
    _matching_cache.move_to_end(key)
    while len(_matching_cache) > MATCHING_CACHE_SIZE:
        _matching_cache.popitem(last=False)


def generation_scope(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        if _request_generations.get() is not None:
            return await func(*args, **kwargs)
        token = _request_generations.set({})
        try:
            return await func(*args, **kwargs)
        finally:
            _request_generations.reset(token)

    return wrapped


def relevance_version() -> str:
    value = os.getenv("SEARCH_RELEVANCE_VERSION", "legacy").strip().lower()
    if value not in {"legacy", "v2"}:
        raise ValueError("SEARCH_RELEVANCE_VERSION must be legacy or v2")
    return value


def is_ordinary_query(query: str | None, search_fields=None, adv_q=None) -> bool:
    if not query or not query.strip() or adv_q:
        return False
    if search_fields and search_fields.strip().lower() != "all_fields":
        return False
    query = query.strip()
    if re.search(r'["():\[\]{}*?~^\\/!<>=|&]', query):
        return False
    if re.search(r"\b(?:AND|OR|NOT)\b|(?:^|\s)[+-]\S", query):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", query):
        return False
    if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", query):
        return False
    # Catalog codes commonly combine letters and numbers with delimiters.
    if re.fullmatch(r"\S+", query) and re.search(r"\d", query) and re.search(r"[-_]", query):
        return False
    return True


def candidate_query(query: str, *, partial: bool = False) -> dict:
    combined = {
        "query": query,
        "fields": [f"{field}.search_en^{weight}" for field, weight in SEARCH_FIELD_WEIGHTS.items()],
        "operator": "or" if partial else "and",
        "zero_terms_query": "none",
    }
    if partial:
        combined["minimum_should_match"] = "2<75%"
    return {"combined_fields": combined}


def text_query(query: str, literal_query: dict, *, partial: bool = False) -> dict:
    literal = copy.deepcopy(literal_query)
    result = {
        "bool": {
            "must": [candidate_query(query, partial=partial)],
            "should": [
                {"term": {"dct_title_s.keyword": {"value": query.lower(), "boost": 20}}},
                {"match_phrase": {"dct_title_s": {"query": query, "boost": 6}}},
                {"bool": {"must": [literal], "boost": 2}},
            ],
        }
    }

    if partial:
        # Conversational filler prevents full-phrase boosts. Reward substantive title
        # coverage and an explicit spatial-label match without inferring a hard filter.
        result["bool"]["should"].extend(
            [
                {
                    "match": {
                        "dct_title_s.search_en": {
                            "query": query,
                            "minimum_should_match": "2<75%",
                            "boost": 6,
                        }
                    }
                },
                {"match": {"dct_spatial_sm.search_en": {"query": query, "boost": 3}}},
            ]
        )
    return result


async def index_generation(es, index: str) -> str:
    """Resolve and validate the concrete index before any v2 response-cache lookup."""
    memo = _request_generations.get()
    key = (id(es), index)
    if memo is not None and key in memo:
        return memo[key]
    response = await es.indices.get_mapping(
        index=index,
        filter_path="*.mappings._meta,*.mappings.properties.*.fields.search_en.analyzer",
    )
    mappings = response.body if hasattr(response, "body") else response
    if len(mappings) != 1:
        raise HTTPException(503, detail="Search relevance requires a single validated index")
    name, entry = next(iter(mappings.items()))
    mapping = entry.get("mappings", {})
    meta = mapping.get("_meta", {})
    properties = mapping.get("properties", {})
    valid = meta.get("search_relevance_ready") is True and meta.get("search_relevance") == "v2"
    valid = valid and all(
        properties.get(field, {}).get("fields", {}).get("search_en", {}).get("analyzer")
        == "catalog_english"
        for field in SEARCH_FIELD_WEIGHTS
    )
    if not valid:
        raise HTTPException(503, detail="Search relevance v2 requires a completed catalog reindex")
    # Index names are versioned; the revision also changes after incremental writes.
    generation = f"{name}:{meta.get('search_revision', 'initial')}"
    if memo is not None:
        memo[key] = generation
        memo[(id(es), name)] = generation
    return generation


@dataclass(frozen=True)
class Matching:
    mode: str = "literal"
    generation: str = "legacy"

    def metadata(self) -> dict:
        return {
            "mode": self.mode,
            "broadened": self.mode == "partial_terms",
            "version": relevance_version(),
        }

    @property
    def cache_token(self) -> str:
        return f"{relevance_version()}:{self.generation}:{self.mode}"


def ensure_complete_response(body: dict) -> None:
    if body.get("timed_out") or body.get("_shards", {}).get("failed", 0):
        raise HTTPException(503, detail="Search execution did not complete")


def _matching_cache_key(strict_query: dict, generation: str) -> str:
    return CacheService().generate_cache_key(
        "search.matching", version="v2", generation=generation, query=strict_query
    )


async def cached_matching(strict_query: dict, generation: str) -> Matching | None:
    key = _matching_cache_key(strict_query, generation)
    local = _matching_cache.get(key)
    if local is not None:
        expires, mode = local
        if expires > time.monotonic():
            _matching_cache.move_to_end(key)
            return Matching(mode, generation)
        del _matching_cache[key]
    cached = await CacheService().get(key)
    if isinstance(cached, str) and cached in {"all_terms", "partial_terms"}:
        _remember_matching(key, cached)
        return Matching(cached, generation)
    return None


async def store_matching(strict_query: dict, matching: Matching) -> None:
    key = _matching_cache_key(strict_query, matching.generation)
    _remember_matching(key, matching.mode)
    await CacheService().set(key, matching.mode, ttl=MATCHING_CACHE_TTL)


async def resolve_matching(es, index: str, strict_query: dict, *, generation: str) -> Matching:
    """Probe the complete logical query, independent of pagination/viewport/autocomplete."""
    cached = await cached_matching(strict_query, generation)
    if cached is not None:
        return cached
    start = time.perf_counter()
    response = await es.search(
        index=index,
        query=strict_query,
        size=0,
        track_total_hits=1,
        terminate_after=1,
        allow_partial_search_results=False,
    )
    body = response.body if hasattr(response, "body") else response
    ensure_complete_response(body)
    total = body["hits"]["total"]
    count = total["value"] if isinstance(total, dict) else total
    mode = "all_terms" if count else "partial_terms"
    matching = Matching(mode, generation)
    await store_matching(strict_query, matching)
    logger.info("Search matching mode=%s probe_ms=%.1f", mode, (time.perf_counter() - start) * 1000)
    return matching
