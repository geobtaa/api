#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const FRONTEND_ROOT = path.resolve(__dirname, '..');
const TEST_ROOT = path.join(FRONTEND_ROOT, 'src', '__tests__');
const TEST_FILE_RE = /\.(test|spec)\.(ts|tsx|js|jsx)$/;
const A11Y_MARKER = 'axeWithWCAG22(';

function walk(dir, files = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }
    if (entry.isFile() && TEST_FILE_RE.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
}

function toPosixRelative(filePath) {
  return path.relative(FRONTEND_ROOT, filePath).split(path.sep).join('/');
}

function collectA11yTests() {
  const testFiles = walk(TEST_ROOT);
  return testFiles
    .filter((filePath) =>
      fs.readFileSync(filePath, 'utf8').includes(A11Y_MARKER)
    )
    .map(toPosixRelative)
    .sort();
}

function run() {
  if (!fs.existsSync(TEST_ROOT)) {
    console.error(`Expected test root not found: ${TEST_ROOT}`);
    process.exit(1);
  }

  const a11yTests = collectA11yTests();
  if (a11yTests.length === 0) {
    console.error(
      'No accessibility tests found (no files containing axeWithWCAG22).'
    );
    process.exit(1);
  }

  console.log(`Running ${a11yTests.length} accessibility test files...`);
  const runner = process.platform === 'win32' ? 'npx.cmd' : 'npx';
  const args = ['vitest', '--run', ...a11yTests];
  const result = spawnSync(runner, args, {
    stdio: 'inherit',
    cwd: FRONTEND_ROOT,
  });

  process.exit(result.status ?? 1);
}

run();
