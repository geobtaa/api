import { Counter, Rate, Trend } from "k6/metrics";

import { config } from "./config.js";

const CACHE_HIT_STATUSES = new Set(["hit", "wait_hit"]);
const CACHE_MISS_STATUSES = new Set(["miss", "wait_miss"]);
const CACHE_DISABLED_STATUSES = new Set(["disabled"]);

const searchResponses = new Counter("search_responses");
const searchStatusResponses = new Counter("search_status_responses");
const searchSemanticCacheObserved = new Counter(
  "search_semantic_cache_observed",
);
const searchSemanticCacheHits = new Counter("search_semantic_cache_hits");
const searchSemanticCacheMisses = new Counter("search_semantic_cache_misses");
const searchSemanticCacheDisabled = new Counter(
  "search_semantic_cache_disabled",
);
const searchSemanticCacheUnknown = new Counter("search_semantic_cache_unknown");
const searchSemanticCacheHitRate = new Rate("search_semantic_cache_hit_rate");

const searchResponseDuration = new Trend("search_response_duration");
const searchServerTimingTotal = new Trend("search_server_timing_total");
const searchServerTimingSearch = new Trend("search_server_timing_search");
const searchServerTimingResponseBuild = new Trend(
  "search_server_timing_response_build",
);
const searchServerTimingResourceCacheLookup = new Trend(
  "search_server_timing_resource_cache_lookup",
);
const searchServerTimingDbFallback = new Trend(
  "search_server_timing_db_fallback",
);
const searchServerTimingMissPrefetch = new Trend(
  "search_server_timing_miss_prefetch",
);
const searchServerTimingMissBuild = new Trend(
  "search_server_timing_miss_build",
);
const searchServerTimingSemanticCacheLookup = new Trend(
  "search_server_timing_semantic_cache_lookup",
);
const searchServerTimingSemanticCacheWait = new Trend(
  "search_server_timing_semantic_cache_wait",
);
const searchServerTimingSemanticCacheStore = new Trend(
  "search_server_timing_semantic_cache_store",
);

const TIMING_METRICS = Object.freeze({
  total: searchServerTimingTotal,
  search: searchServerTimingSearch,
  response_build: searchServerTimingResponseBuild,
  resource_cache_lookup: searchServerTimingResourceCacheLookup,
  db_fallback: searchServerTimingDbFallback,
  miss_prefetch: searchServerTimingMissPrefetch,
  miss_build: searchServerTimingMissBuild,
  semantic_cache_lookup: searchServerTimingSemanticCacheLookup,
  semantic_cache_wait: searchServerTimingSemanticCacheWait,
  semantic_cache_store: searchServerTimingSemanticCacheStore,
});

function header(response, name) {
  return (
    response.headers[name] ||
    response.headers[name.toLowerCase()] ||
    response.headers[name.toUpperCase()] ||
    ""
  );
}

function normalizeStatus(value) {
  const normalized = String(value || "")
    .trim()
    .replace(/^"|"$/g, "")
    .toLowerCase();

  return normalized || "unreported";
}

function parseServerTiming(value) {
  const parsed = {};
  if (!value) {
    return parsed;
  }

  for (const item of String(value).split(",")) {
    const parts = item
      .trim()
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length === 0) {
      continue;
    }

    const metricName = parts[0];
    parsed[metricName] = parsed[metricName] || {};

    for (const param of parts.slice(1)) {
      const separator = param.indexOf("=");
      if (separator === -1) {
        parsed[metricName][param] = true;
        continue;
      }

      const key = param.slice(0, separator).trim();
      const rawValue = param
        .slice(separator + 1)
        .trim()
        .replace(/^"|"$/g, "");
      parsed[metricName][key] = rawValue;
    }
  }

  return parsed;
}

function semanticCacheStatus(response, serverTiming) {
  const explicitHeader = header(response, "X-Search-Semantic-Cache");
  if (explicitHeader) {
    return normalizeStatus(explicitHeader);
  }

  return normalizeStatus(serverTiming.semantic_cache?.desc);
}

export function recordSearchDiagnostics(response, endpointName, options = {}) {
  if (!config.searchDiagnostics) {
    return;
  }

  const expectSemanticCache = options.expectSemanticCache !== false;
  const serverTiming = parseServerTiming(header(response, "Server-Timing"));
  const cacheStatus = semanticCacheStatus(response, serverTiming);
  const tags = {
    endpoint: endpointName,
    semantic_cache_status: cacheStatus,
    status: String(response.status),
  };

  searchResponses.add(1, tags);
  searchStatusResponses.add(1, tags);
  searchResponseDuration.add(response.timings.duration, tags);

  if (expectSemanticCache) {
    if (cacheStatus === "unreported") {
      searchSemanticCacheUnknown.add(1, tags);
    } else {
      searchSemanticCacheObserved.add(1, tags);
      searchSemanticCacheHitRate.add(CACHE_HIT_STATUSES.has(cacheStatus), tags);

      if (CACHE_HIT_STATUSES.has(cacheStatus)) {
        searchSemanticCacheHits.add(1, tags);
      } else if (CACHE_MISS_STATUSES.has(cacheStatus)) {
        searchSemanticCacheMisses.add(1, tags);
      } else if (CACHE_DISABLED_STATUSES.has(cacheStatus)) {
        searchSemanticCacheDisabled.add(1, tags);
      } else {
        searchSemanticCacheUnknown.add(1, tags);
      }
    }
  }

  for (const [timingName, metric] of Object.entries(TIMING_METRICS)) {
    const duration = Number.parseFloat(serverTiming[timingName]?.dur);
    if (Number.isFinite(duration)) {
      metric.add(duration, tags);
    }
  }
}
