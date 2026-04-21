import { describe, expect, it } from 'vitest';
import {
  isSuspiciousViewState,
  resolveUseWgs84ExtentForFit,
  shouldUseWgs84ExtentForFit,
} from '../../utils/openlayersViewFit';

describe('openlayersViewFit', () => {
  describe('shouldUseWgs84ExtentForFit', () => {
    it('uses WGS84 for PMTiles when user projection is geographic', () => {
      expect(
        shouldUseWgs84ExtentForFit('pmtiles', 'EPSG:3857', 'EPSG:4326')
      ).toBe(true);
    });

    it('does not force WGS84 for PMTiles when user projection is not geographic', () => {
      expect(shouldUseWgs84ExtentForFit('pmtiles', 'EPSG:3857')).toBe(false);
    });

    it('uses WGS84 for EPSG:4326 regardless of protocol', () => {
      expect(shouldUseWgs84ExtentForFit('cog', 'EPSG:4326')).toBe(true);
    });

    it('uses transformed extent for non-PMTiles non-4326 projections', () => {
      expect(shouldUseWgs84ExtentForFit('cog', 'EPSG:3857')).toBe(false);
    });
  });

  describe('isSuspiciousViewState', () => {
    it('flags non-finite centers as suspicious', () => {
      expect(
        isSuspiciousViewState({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:3857',
          center: [Number.NaN, Number.NaN],
          zoom: 11.14,
        })
      ).toBe(true);
    });

    it('flags PMTiles lon/lat-looking center in a 3857 view as suspicious', () => {
      expect(
        isSuspiciousViewState({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:3857',
          userProjectionCode: 'EPSG:4326',
          center: [-75.118, 40.0028],
          zoom: 11.14,
        })
      ).toBe(true);
    });

    it('flags PMTiles center values that look projected instead of lon/lat', () => {
      expect(
        isSuspiciousViewState({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:3857',
          userProjectionCode: 'EPSG:4326',
          center: [-8362097.5, 62.78],
          zoom: 11.14,
        })
      ).toBe(true);
    });

    it('does not flag valid projected PMTiles center when user projection is absent', () => {
      expect(
        isSuspiciousViewState({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:3857',
          center: [-8362097.5, 4866354.1],
          zoom: 11.14,
        })
      ).toBe(false);
    });

    it('flags low world-view zooms for any protocol', () => {
      expect(
        isSuspiciousViewState({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:4326',
          center: [-75.118, 40.0028],
          zoom: 2.1,
        })
      ).toBe(true);
    });

    it('does not flag a valid EPSG:3857 COG center with reasonable zoom', () => {
      expect(
        isSuspiciousViewState({
          protocol: 'cog',
          projectionCode: 'EPSG:3857',
          center: [-8362097.5, 4866354.1],
          zoom: 11.1,
        })
      ).toBe(false);
    });
  });

  describe('resolveUseWgs84ExtentForFit', () => {
    it('chooses projected fit for PMTiles when current center is projected meters', () => {
      expect(
        resolveUseWgs84ExtentForFit({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:3857',
          currentCenter: [-8362097.5, 4866354.1],
        })
      ).toBe(false);
    });

    it('chooses WGS84 fit for PMTiles when current center has mixed signature', () => {
      expect(
        resolveUseWgs84ExtentForFit({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:3857',
          currentCenter: [-8362097.5, 62.78],
        })
      ).toBe(true);
    });

    it('chooses projected fit for PMTiles when current center looks like lon/lat in a 3857 view', () => {
      expect(
        resolveUseWgs84ExtentForFit({
          protocol: 'pmtiles',
          projectionCode: 'EPSG:3857',
          currentCenter: [-75.118, 40.0027],
        })
      ).toBe(false);
    });
  });
});
