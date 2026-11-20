import { expect, it } from 'vitest';
import { decodeId, encodeId, resourceApiPath, resourcePath } from './urlIds';

it.each([
  ['plain-id_123', 'plain-id_123'],
  ['editor/test', '~ZWRpdG9yL3Rlc3Q'],
  ['map/1', '~bWFwLzE'],
  ['new', '~bmV3'],
  ['facets', '~ZmFjZXRz'],
  ['.', '~Lg'],
  ['..', '~Li4'],
  ['~', '~fg'],
])('uses a canonical single segment for %s', (id, key) => {
  expect(encodeId(id)).toBe(key);
  expect(decodeId(key)).toBe(id);
  expect(resourcePath(id)).toBe(`/resources/${key}`);
  expect(resourceApiPath(id)).toBe(`/api/v1/admin/resources/${key}`);
});

it.each([
  'é/地图',
  'map/relationships',
  'facets/field',
  '/leading',
  'trailing/',
  'a%2Fb',
  'a?b#c',
  'white space',
  '😀'.repeat(512),
])('preserves the exact metadata ID %s', (id) => {
  const key = encodeId(id);
  expect(key).not.toMatch(/[/?#]/);
  expect(decodeId(key)).toBe(id);
});

it.each([
  '',
  '~',
  '~?',
  '~_w',
  '~YQ==',
  '~YQ',
  '~IA',
  '~AA',
  '~Y',
  'new',
  'a/b',
  'x'.repeat(513),
])('rejects invalid and noncanonical keys %s', (key) => {
  expect(decodeId(key)).toBe('');
});
