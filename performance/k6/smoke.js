import { config } from './lib/config.js';
import { apiFlow, frontendFlow, setupSeed } from './lib/flows.js';

export const options = {
  vus: config.smokeVus,
  iterations: config.smokeIterations,
  thresholds: {
    checks: ['rate>0.99'],
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<5000'],
  },
};

export function setup() {
  return setupSeed();
}

export default function (seed) {
  if (config.enableFrontend) {
    frontendFlow(seed);
  }

  if (config.enableApi) {
    apiFlow(seed);
  }
}
