const DEFAULT_BASE_URL = "https://lib-btaageoapi-dev-app-01.oit.umn.edu";
const DEFAULT_QUERY = "minnesota";
const FALSE_VALUES = new Set(["0", "false", "FALSE", "False", "no", "NO"]);

function intEnv(name, fallback) {
  const value = __ENV[name];
  if (!value) {
    return fallback;
  }

  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) {
    throw new Error(`${name} must be an integer, got "${value}"`);
  }

  return parsed;
}

function floatEnv(name, fallback) {
  const value = __ENV[name];
  if (!value) {
    return fallback;
  }

  const parsed = Number.parseFloat(value);
  if (Number.isNaN(parsed)) {
    throw new Error(`${name} must be a number, got "${value}"`);
  }

  return parsed;
}

function enabledEnv(name, fallback = true) {
  const value = __ENV[name];
  if (!value) {
    return fallback;
  }

  return !FALSE_VALUES.has(value);
}

function listEnv(name) {
  const value = __ENV[name];
  if (!value) {
    return [];
  }

  return value
    .split(/[|,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export const config = Object.freeze({
  baseUrl: (__ENV.K6_BASE_URL || DEFAULT_BASE_URL).replace(/\/+$/, ""),
  query: __ENV.K6_QUERY || DEFAULT_QUERY,
  queryPool: listEnv("K6_QUERY_POOL"),
  apiKey: __ENV.K6_API_KEY || __ENV.BTAA_GEOSPATIAL_API_KEY || "",
  suggestQuery: __ENV.K6_SUGGEST_QUERY || "",
  resourceId: __ENV.K6_RESOURCE_ID || "",
  searchPerPage: intEnv("K6_SEARCH_PER_PAGE", 10),
  cacheBustSearch: enabledEnv("K6_CACHE_BUST_SEARCH", false),
  cacheBustSeed:
    __ENV.K6_CACHE_BUST_SEED ||
    `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  endpointBreakdown: enabledEnv("K6_ENDPOINT_BREAKDOWN", false),
  searchDiagnostics: enabledEnv("K6_SEARCH_DIAGNOSTICS", true),
  enableFrontend: enabledEnv("K6_ENABLE_FRONTEND", true),
  enableApi: enabledEnv("K6_ENABLE_API", true),
  frontendTargetVus: intEnv("K6_FRONTEND_TARGET_VUS", 4),
  frontendRampUp: __ENV.K6_FRONTEND_RAMP_UP || "30s",
  frontendHold: __ENV.K6_FRONTEND_HOLD || "2m",
  frontendRampDown: __ENV.K6_FRONTEND_RAMP_DOWN || "30s",
  frontendThinkTimeSeconds: floatEnv("K6_FRONTEND_THINK_TIME_SECONDS", 1),
  frontendP95ThresholdMs: intEnv("K6_FRONTEND_P95_THRESHOLD_MS", 2500),
  frontendP99ThresholdMs: intEnv("K6_FRONTEND_P99_THRESHOLD_MS", 5000),
  apiTargetVus: intEnv("K6_API_TARGET_VUS", 8),
  apiRampUp: __ENV.K6_API_RAMP_UP || "30s",
  apiHold: __ENV.K6_API_HOLD || "2m",
  apiRampDown: __ENV.K6_API_RAMP_DOWN || "30s",
  apiThinkTimeSeconds: floatEnv("K6_API_THINK_TIME_SECONDS", 0.25),
  apiP95ThresholdMs: intEnv("K6_API_P95_THRESHOLD_MS", 1500),
  apiP99ThresholdMs: intEnv("K6_API_P99_THRESHOLD_MS", 3000),
  smokeVus: intEnv("K6_SMOKE_VUS", 1),
  smokeIterations: intEnv("K6_SMOKE_ITERATIONS", 1),
});

export function buildStages(target, rampUp, hold, rampDown) {
  return [
    { duration: rampUp, target },
    { duration: hold, target },
    { duration: rampDown, target: 0 },
  ];
}
