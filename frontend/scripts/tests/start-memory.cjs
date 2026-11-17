const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const frontend = path.resolve(__dirname, '../..');
const start = JSON.parse(
  fs.readFileSync(path.join(frontend, 'package.json'), 'utf8')
).scripts.start;

function launch(nodeOptions) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssr-start-test-'));
  try {
    fs.mkdirSync(path.join(dir, 'bin'));
    fs.mkdirSync(path.join(dir, 'node_modules/source-map-support'), {
      recursive: true,
    });
    fs.writeFileSync(
      path.join(dir, 'appsignal.cjs'),
      'global.preloads = ["appsignal"];'
    );
    fs.writeFileSync(
      path.join(dir, 'node_modules/source-map-support/register.js'),
      'global.preloads.push("source-map");'
    );
    fs.writeFileSync(
      path.join(dir, 'custom.cjs'),
      'global.preloads.push("custom");'
    );
    fs.writeFileSync(
      path.join(dir, 'probe.cjs'),
      `console.log(JSON.stringify({
      heap: require('node:v8').getHeapStatistics().heap_size_limit,
      stackTraceLimit: Error.stackTraceLimit,
      preloads: global.preloads,
      args: process.argv.slice(2)
    }));`
    );
    fs.writeFileSync(
      path.join(dir, 'bin/react-router-serve'),
      '#!/bin/sh\nexec "$TEST_NODE" ./probe.cjs "$@"\n',
      { mode: 0o755 }
    );
    const env = {
      ...process.env,
      TEST_NODE: process.execPath,
      PATH: `${dir}/bin:${process.env.PATH}`,
    };
    delete env.NODE_OPTIONS;
    if (nodeOptions !== undefined) env.NODE_OPTIONS = nodeOptions;
    const result = spawnSync('/bin/sh', ['-c', start], {
      cwd: dir,
      env,
      encoding: 'utf8',
    });
    assert.equal(result.status, 0, result.stderr);
    return JSON.parse(result.stdout);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('SSR start preserves the heap budget and other inherited Node options', () => {
  const result = launch(
    '--max-old-space-size=512 --stack-trace-limit=37 --require ./custom.cjs'
  );
  assert.ok(result.heap >= 512 * 1024 ** 2 && result.heap < 600 * 1024 ** 2);
  assert.equal(result.stackTraceLimit, 37);
  assert.deepEqual(result.preloads, ['appsignal', 'source-map', 'custom']);
  assert.deepEqual(result.args, ['./build/server/index.js']);
});

for (const options of [undefined, '']) {
  test(`SSR start still loads instrumentation with ${options === undefined ? 'unset' : 'empty'} Node options`, () => {
    assert.deepEqual(launch(options).preloads, ['appsignal', 'source-map']);
  });
}

test('invalid SSR heap budgets fail before starting application processes', () => {
  const script = path.join(
    frontend,
    '../backend/scripts/start_web_singlehost.sh'
  );
  for (const budget of ['0', '-1', '1.5', '512mb', '512 --inspect', 'abc']) {
    const result = spawnSync('bash', [script], {
      env: {
        ...process.env,
        WEB_SSR_MAX_OLD_SPACE_MB: budget,
        WEB_SSR_WORKERS: '2',
      },
      encoding: 'utf8',
    });
    assert.equal(result.status, 1);
    assert.match(
      result.stderr,
      /WEB_SSR_MAX_OLD_SPACE_MB must be a positive integer/
    );
    assert.doesNotMatch(result.stdout, /starting/);
  }
});
