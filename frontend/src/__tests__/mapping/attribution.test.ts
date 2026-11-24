import { expect, it, vi } from 'vitest';
import { collapseInitialAttribution } from '../../mapping/attribution';
import type { Map } from 'maplibre-gl';
it('collapses asynchronously loaded attribution once, leaving user toggles alone', () => {
  const container = document.createElement('div');
  container.innerHTML =
    '<details class="maplibregl-ctrl-attrib maplibregl-attrib-empty"><summary>Information</summary>Attribution</details>';
  const events = new globalThis.Map<string, () => void>();
  const map = {
    getContainer: () => container,
    on: vi.fn((name, callback) => events.set(name, callback)),
    off: vi.fn((name) => events.delete(name)),
  };
  const cleanup = collapseInitialAttribution(map as unknown as Map);
  expect(events.size).toBe(2);
  const details = container.querySelector('details')!;
  details.className =
    'maplibregl-ctrl-attrib maplibregl-compact maplibregl-compact-show';
  details.open = true;
  events.get('sourcedata')!();
  expect(details.open).toBe(false);
  expect(details.classList.contains('maplibregl-compact-show')).toBe(false);
  expect(events.size).toBe(0);
  details.open = true;
  expect(details.open).toBe(true);
  cleanup();
});
it('removes pending readiness listeners on map cleanup', () => {
  const map = {
    getContainer: () => document.createElement('div'),
    on: vi.fn(),
    off: vi.fn(),
  };
  const cleanup = collapseInitialAttribution(map as unknown as Map);
  cleanup();
  expect(map.off).toHaveBeenCalledWith('styledata', expect.any(Function));
  expect(map.off).toHaveBeenCalledWith('sourcedata', expect.any(Function));
});
