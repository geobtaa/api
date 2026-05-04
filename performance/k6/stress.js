import { buildStages, config } from './lib/config.js';
import { apiFlow, frontendFlow, setupSeed } from './lib/flows.js';

const ENDPOINT_NAMES = [
  'frontend_home_page',
  'frontend_manifest',
  'frontend_service_worker',
  'frontend_search_page',
  'frontend_search_results_api',
  'frontend_faceted_search_page',
  'frontend_faceted_search_results_api',
  'frontend_resource_page',
  'api_search',
  'api_faceted_search',
  'api_suggest',
  'api_resource_list',
  'api_resource_detail',
  'api_facet_values',
  'api_home_blog',
];

if (!config.enableFrontend && !config.enableApi) {
  throw new Error('At least one of K6_ENABLE_FRONTEND or K6_ENABLE_API must be enabled.');
}

const scenarios = {};
const thresholds = {
  checks: ['rate>0.98'],
  http_req_failed: ['rate<0.02'],
};

if (config.enableFrontend) {
  scenarios.frontend_pages = {
    executor: 'ramping-vus',
    exec: 'frontendPages',
    startVUs: 1,
    stages: buildStages(
      config.frontendTargetVus,
      config.frontendRampUp,
      config.frontendHold,
      config.frontendRampDown
    ),
    gracefulRampDown: '30s',
    tags: { surface: 'frontend' },
  };
  thresholds['http_req_duration{scenario:frontend_pages}'] = [
    'p(95)<2500',
    'p(99)<5000',
  ];
}

if (config.enableApi) {
  scenarios.api_endpoints = {
    executor: 'ramping-vus',
    exec: 'apiEndpoints',
    startVUs: 1,
    stages: buildStages(
      config.apiTargetVus,
      config.apiRampUp,
      config.apiHold,
      config.apiRampDown
    ),
    gracefulRampDown: '30s',
    tags: { surface: 'api' },
  };
  thresholds['http_req_duration{scenario:api_endpoints}'] = [
    'p(95)<1500',
    'p(99)<3000',
  ];
}

if (config.endpointBreakdown) {
  for (const endpointName of ENDPOINT_NAMES) {
    thresholds[`http_req_duration{name:${endpointName}}`] = ['p(95)<60000', 'p(99)<60000'];
  }
}

export const options = {
  scenarios,
  thresholds,
};

export function setup() {
  return setupSeed();
}

export function frontendPages(seed) {
  frontendFlow(seed);
}

export function apiEndpoints(seed) {
  apiFlow(seed);
}
