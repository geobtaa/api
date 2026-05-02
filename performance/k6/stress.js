import { buildStages, config } from './lib/config.js';
import { apiFlow, frontendFlow, setupSeed } from './lib/flows.js';

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
