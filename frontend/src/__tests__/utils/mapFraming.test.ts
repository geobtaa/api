import { describe, it, expect, vi } from 'vitest';
import { LngLatBounds } from 'maplibre-gl';
import type { OgmRecord, Resource } from 'ogm-viewer/lib';
import {
  geojsonFramingBounds,
  unionFramingBounds,
  frameViewerRecord,
} from '../../utils/mapFraming';
const polygon = (west: number, east: number, south = 0, north = 1) => ({
  type: 'Polygon',
  coordinates: [
    [
      [west, south],
      [east, south],
      [east, north],
      [west, north],
      [west, south],
    ],
  ],
});
const collection = (...geometries: unknown[]) => ({
  type: 'FeatureCollection',
  features: geometries.map((geometry) => ({ type: 'Feature', geometry })),
});
const source = (data: unknown) =>
  ({
    kind: 'openindexmap',
    getData: vi.fn().mockResolvedValue(data),
  }) as unknown as Resource;
const record = (bounds?: [number, number, number, number]) =>
  ({
    json: { id: 'unchanged' },
    getBounds: () => (bounds ? new LngLatBounds(bounds) : undefined),
    getGeometry: () => polygon(-180, 180),
  }) as unknown as OgmRecord;
describe('shared data-informed framing', () => {
  it('frames a dateline crossing narrowly', () => {
    expect(geojsonFramingBounds(polygon(179, -179))).toEqual([179, 0, 181, 1]);
  });
  it('preserves explicit global geometry', () => {
    expect(geojsonFramingBounds(polygon(-180, 180, -90, 90))).toEqual([
      -180, -90, 180, 90,
    ]);
  });
  it('preserves North American and Pacific coverage in a single wrapped extent', () => {
    expect(
      geojsonFramingBounds(
        collection(
          polygon(134, 135, -15, -14),
          polygon(-180, -179, 50, 51),
          polygon(-53, -52, 83, 84)
        )
      )
    ).toEqual([134, -15, 308, 84]);
  });
  it('keeps lines, points and holes in the framing calculation', () => {
    expect(
      geojsonFramingBounds(
        collection(
          { type: 'Point', coordinates: [-100, 40] },
          {
            type: 'LineString',
            coordinates: [
              [-110, 30],
              [-90, 50],
            ],
          },
          polygon(-105, -95, 35, 45)
        )
      )
    ).toEqual([-110, 30, -90, 50]);
  });
  it('rejects empty and invalid data', () => {
    expect(geojsonFramingBounds(collection())).toBeUndefined();
    expect(
      geojsonFramingBounds({ type: 'Point', coordinates: [0, 100] })
    ).toBeUndefined();
  });
  it('unions overlapping longitude intervals without dropping covered space', () => {
    expect(
      unionFramingBounds([
        [-170, 0, 0, 10],
        [-10, 0, 160, 20],
      ])
    ).toEqual([-170, 0, 160, 20]);
  });
  it('leaves useful record bounds alone', async () => {
    const r = record([-100, 30, -80, 50]),
      s = source(collection(polygon(134, 135)));
    expect(await frameViewerRecord(r, [s])).toBe(r);
    expect(
      (s as unknown as { getData: unknown }).getData
    ).not.toHaveBeenCalled();
  });
  it('changes the camera accessor without changing metadata or coverage', async () => {
    const r = record([-180, -15, 180, 84]);
    const framed = await frameViewerRecord(r, [
      source(collection(polygon(134, 135), polygon(-53, -52))),
    ]);
    expect(framed.getBounds().toArray()).toEqual([
      [134, 0],
      [308, 1],
    ]);
    expect(framed.json).toBe(r.json);
    expect(framed.getGeometry()).toEqual(r.getGeometry());
    expect(r.getBounds().getWest()).toBe(-180);
  });
  it('uses source bounds when metadata is missing', async () => {
    const framed = await frameViewerRecord(record(), [
      {
        kind: 'tilejson',
        getReportedBounds: async () => [-110, 30, -90, 50],
      } as unknown as Resource,
    ]);
    expect(framed.getBounds().toArray()).toEqual([
      [-110, 30],
      [-90, 50],
    ]);
  });
  it('keeps the fallback when any source fails', async () => {
    const r = record([-180, -90, 180, 90]);
    expect(
      await frameViewerRecord(r, [
        source(collection(polygon(-100, -90))),
        {
          kind: 'wms',
          getReportedBounds: async () => {
            throw Error('unavailable');
          },
        } as unknown as Resource,
      ])
    ).toBe(r);
  });
  it('bounds initial waiting time when a source never responds', async () => {
    vi.useFakeTimers();
    try {
      const r = record();
      const result = frameViewerRecord(r, [
        {
          kind: 'wms',
          getReportedBounds: () => new Promise(() => {}),
        } as unknown as Resource,
      ]);
      await vi.advanceTimersByTimeAsync(5000);
      expect(await result).toBe(r);
    } finally {
      vi.useRealTimers();
    }
  });
});
