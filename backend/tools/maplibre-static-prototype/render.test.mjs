import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fitBounds } from './render.mjs';
test('Mercator bounds fit respects padding and centers projected latitude', () => {
  const result = fitBounds([-10, -10, 10, 10], 800, 600);
  assert.ok(Math.abs(result.center[0]) < 1e-10);
  assert.ok(Math.abs(result.center[1]) < 1e-10);
  assert.ok(result.zoom > 4 && result.zoom < 5);
});
test('invalid and dateline-crossing bounds fail explicitly', () => {
  assert.throws(() => fitBounds([170, -10, -170, 10], 800, 600));
  assert.throws(() => fitBounds([-10, -90, 10, 90], 800, 600));
});
