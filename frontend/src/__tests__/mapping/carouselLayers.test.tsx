import { memo } from 'react';
import { act, render } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { MapContainer, useMap } from '../../mapping/react';
import { MapUpdaterHex } from '../../components/map/MapUpdaterHex';

const state = vi.hoisted(() => ({
  zoom: 3,
  events: new Map<string, Set<() => void>>(),
  removeLayer: vi.fn(),
  createLayer: vi.fn(),
  fetchHexes: vi.fn(),
  consumerRender: vi.fn(),
}));
vi.mock('../../mapping/maplibre', () => {
  class Map {
    getZoom = () => state.zoom;
    getBounds = () => ({
      getWest: () => -100,
      getSouth: () => 30,
      getEast: () => -70,
      getNorth: () => 50,
    });
    whenReady = (callback: () => void) => callback();
    getContainer = () => document.createElement('div');
    on = (name: string, callback: () => void) => {
      if (!state.events.has(name)) state.events.set(name, new Set());
      state.events.get(name)!.add(callback);
    };
    off = (name: string, callback: () => void) => {
      state.events.get(name)?.delete(callback);
    };
    remove = vi.fn();
  }
  return {
    Map,
    geoJSON: (...args: unknown[]) => {
      state.createLayer(...args);
      return { addTo: () => ({ remove: state.removeLayer }) };
    },
  };
});
const hexes = [{ h3: '822a17fffffffff', count: 12 }];
vi.mock('../../hooks/useMapH3', () => ({
  useMapH3: (...args: unknown[]) => {
    state.fetchHexes(...args);
    return { hexes, hexCount: 1, totalInView: 12, loading: false, error: null };
  },
}));
const onFeatureClick = () => {};
const Consumer = memo(function Consumer() {
  useMap();
  state.consumerRender();
  return null;
});
function Scene({ progress, query = '' }: { progress: number; query?: string }) {
  return (
    <MapContainer center={[44, -80]} zoom={3}>
      <span>{progress}</span>
      <Consumer />
      <MapUpdaterHex searchQuery={query} onFeatureClick={onFeatureClick} />
    </MapContainer>
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  state.events.clear();
  state.zoom = 3;
});
it('keeps hex sources and map context stable across carousel progress ticks', () => {
  const view = render(<Scene progress={100} />);
  const sources = state.createLayer.mock.calls.length;
  const removals = state.removeLayer.mock.calls.length;
  const consumers = state.consumerRender.mock.calls.length;
  for (let progress = 99; progress > 90; progress--)
    view.rerender(<Scene progress={progress} />);
  expect(state.createLayer).toHaveBeenCalledTimes(sources);
  expect(state.removeLayer).toHaveBeenCalledTimes(removals);
  expect(state.consumerRender).toHaveBeenCalledTimes(consumers);
  view.unmount();
  expect(state.removeLayer).toHaveBeenCalledTimes(removals + 1);
});
it('updates H3 resolution after the flight settles, even with prop changes mid-flight', () => {
  const view = render(<Scene progress={100} />);
  state.zoom = 9;
  view.rerender(<Scene progress={50} query="changed" />);
  expect(state.fetchHexes.mock.lastCall?.[2]).toBe(2);
  act(() => state.events.get('moveend')?.forEach((callback) => callback()));
  expect(state.fetchHexes.mock.lastCall?.[2]).toBe(6);
  const sources = state.createLayer.mock.calls.length;
  act(() => state.events.get('zoomend')?.forEach((callback) => callback()));
  expect(state.createLayer).toHaveBeenCalledTimes(sources);
});
