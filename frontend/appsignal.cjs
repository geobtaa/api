const { Appsignal } = require('@appsignal/nodejs');
const { RemixInstrumentation } = require('opentelemetry-instrumentation-remix');

function envFirst(...names) {
  for (const name of names) {
    const value = process.env[name];
    if (value) {
      return value;
    }
  }
  return undefined;
}

function envFlag(name, defaultValue = 'true') {
  return !['0', 'false', 'no', 'off'].includes(
    String(process.env[name] ?? defaultValue)
      .trim()
      .toLowerCase()
  );
}

function envInt(name, defaultValue) {
  return Number.parseInt(process.env[name] ?? defaultValue, 10);
}

function envList(...names) {
  for (const name of names) {
    if (Object.prototype.hasOwnProperty.call(process.env, name)) {
      return String(process.env[name] ?? '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
    }
  }
  return [];
}

const appsignalActive = envFlag(
  'APPSIGNAL_FRONTEND_ACTIVE',
  process.env.APPSIGNAL_ACTIVE ?? 'true'
);

new Appsignal({
  active: appsignalActive,
  name:
    envFirst('APPSIGNAL_FRONTEND_APP_NAME', 'APPSIGNAL_APP_NAME') ||
    'BTAA Geoportal SSR',
  environment: envFirst('APPSIGNAL_FRONTEND_APP_ENV', 'APPSIGNAL_APP_ENV'),
  revision: process.env.APP_REVISION,
  enableHostMetrics: envFlag(
    'APPSIGNAL_FRONTEND_ENABLE_HOST_METRICS',
    process.env.APPSIGNAL_ENABLE_HOST_METRICS ?? 'false'
  ),
  hostRole:
    envFirst('APPSIGNAL_FRONTEND_HOST_ROLE', 'APPSIGNAL_HOST_ROLE') ||
    'frontend',
  workingDirectoryPath:
    envFirst(
      'APPSIGNAL_FRONTEND_WORKING_DIRECTORY_PATH',
      'APPSIGNAL_WORKING_DIRECTORY_PATH'
    ) || '/tmp/appsignal-frontend',
  ignoreErrors: envList(
    'APPSIGNAL_FRONTEND_IGNORE_ERRORS',
    'APPSIGNAL_IGNORE_ERRORS'
  ),
  opentelemetryPort: envInt('APPSIGNAL_FRONTEND_OPENTELEMETRY_PORT', '8100'),
  additionalInstrumentations: [new RemixInstrumentation()],
});
