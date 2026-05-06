import { config } from "./lib/config.js";
import {
  requestApiFacetedSearch,
  requestApiSearch,
  requestFrontendFacetedSearchResultsApi,
  requestFrontendResourcePage,
  requestFrontendSearchResultsApi,
  setupSeed,
} from "./lib/flows.js";

const ENDPOINTS = {
  api_faceted_search: requestApiFacetedSearch,
  api_search: requestApiSearch,
  frontend_faceted_search_results_api: requestFrontendFacetedSearchResultsApi,
  frontend_resource_page: requestFrontendResourcePage,
  frontend_search_results_api: requestFrontendSearchResultsApi,
};

const endpointRunner = ENDPOINTS[config.endpointTarget];

if (!endpointRunner) {
  throw new Error(
    `Unknown K6_ENDPOINT_TARGET "${config.endpointTarget}". ` +
      `Expected one of: ${Object.keys(ENDPOINTS).join(", ")}`,
  );
}

export const options = {
  scenarios: {
    endpoint_capacity: {
      executor: "constant-arrival-rate",
      rate: config.requestRate,
      timeUnit: config.rateTimeUnit,
      duration: config.endpointDuration,
      preAllocatedVUs: config.preAllocatedVus,
      maxVUs: config.maxVus,
      exec: "endpointCapacity",
      tags: {
        endpoint_target: config.endpointTarget,
        surface: config.endpointTarget.startsWith("frontend_")
          ? "frontend"
          : "api",
      },
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    dropped_iterations: ["count==0"],
    http_req_failed: ["rate<0.01"],
    [`http_req_duration{name:${config.endpointTarget}}`]: [
      `p(95)<${config.endpointP95ThresholdMs}`,
      `p(99)<${config.endpointP99ThresholdMs}`,
    ],
  },
};

export function setup() {
  return setupSeed();
}

export function endpointCapacity(seed) {
  endpointRunner(seed);
}
