import { describe, expect, it } from 'vitest';
import { cellToBoundary, latLngToCell } from 'h3-js';
import { h3CellGeometry, getHexBoundingBox } from '../../utils/h3Geometry';

describe('h3CellGeometry', () => {
  it('preserves an ordinary cell as a closed GeoJSON polygon', () => {
    const cell = latLngToCell(43, -89, 3);
    const ring = cellToBoundary(cell).map(([lat, lng]) => [lng, lat]);
    expect(h3CellGeometry(cell)).toEqual({
      type: 'Polygon',
      coordinates: [[...ring, ring[0]]],
    });
  });

  for (const resolution of [2, 3, 4, 5, 6, 7, 8]) {
    for (const latitude of [-45, 0, 45]) {
      it(`splits dateline cells at latitude ${latitude}, resolution ${resolution}`, () => {
        const cell = latLngToCell(latitude, 180, resolution);
        const geometry = h3CellGeometry(cell);
        expect(geometry.type).toBe('MultiPolygon');
        if (geometry.type !== 'MultiPolygon')
          throw new Error('Expected split cell');
        expect(geometry.coordinates).toHaveLength(2);
        const seams: number[][] = [];
        for (const [ring] of geometry.coordinates) {
          expect(ring.length).toBeGreaterThanOrEqual(4);
          expect(ring[0]).toEqual(ring[ring.length - 1]);
          seams.push(
            ring.filter(([lng]) => Math.abs(lng) === 180).map(([, lat]) => lat)
          );
          for (let i = 0; i < ring.length - 1; i++) {
            const [lng, lat] = ring[i];
            expect(lng).toBeGreaterThanOrEqual(-180);
            expect(lng).toBeLessThanOrEqual(180);
            expect(Number.isFinite(lat)).toBe(true);
            expect(Math.abs(lng - ring[i + 1][0])).toBeLessThan(180);
          }
        }
        // Both pieces meet at exactly the same interpolated latitudes.
        expect([...new Set(seams[0])].sort()).toEqual(
          [...new Set(seams[1])].sort()
        );
      });
    }
  }
});

describe('getHexBoundingBox', () => {
  it('keeps ordinary cells within their original longitude bounds', () => {
    const cell = latLngToCell(43, -89, 3);
    const vertices = cellToBoundary(cell);
    const bbox = getHexBoundingBox(cell);
    expect(bbox.west).toBe(Math.min(...vertices.map(([, lng]) => lng)));
    expect(bbox.east).toBe(Math.max(...vertices.map(([, lng]) => lng)));
  });

  it('uses the short dateline interval for the hex reported in issue 392', () => {
    const cell = latLngToCell(-18.4, 180, 2);
    const bbox = getHexBoundingBox(cell);
    expect(bbox.north).toBeCloseTo(-16.8200620584835, 8);
    expect(bbox.south).toBeCloseTo(-19.974201675100904, 8);
    expect(bbox.west).toBeGreaterThan(170);
    expect(bbox.east).toBeLessThan(-170);
    expect(bbox.east + 360 - bbox.west).toBeLessThan(5);
    const geometry = h3CellGeometry(cell);
    expect(geometry.type).toBe('MultiPolygon');
  });
});
