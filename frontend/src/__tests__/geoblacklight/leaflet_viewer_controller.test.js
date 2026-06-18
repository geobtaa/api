import Leaflet from 'leaflet';
import { describe, expect, it } from 'vitest';
import {
  EMPTY_IIIF_TILE_URL,
  getIiifImageBounds,
  getIiifLeafletMapOptions,
  getIiifMaxNativeZoom,
  getIiifTileUrl,
  IIIF_MIN_ZOOM,
  normalizeIiifImageServiceId,
  resizeIiifTileToNaturalSize,
} from '../../geoblacklight/iiif_image_layer';

const baseTileOptions = {
  imageApiVersion: 2,
  imageHeight: 6270,
  imageWidth: 7392,
  maxNativeZoom: 3,
  serviceId:
    'https://s3.amazonaws.com/ogm-metadata-studio/uploads/unr-74479f22-0e6b-4c13-b376-0195a7461525/iiif',
  tileFormat: 'jpg',
  tileQuality: 'default',
  tileSize: 1024,
};

describe('Leaflet IIIF helpers', () => {
  it('computes the native zoom from IIIF image dimensions and tile size', () => {
    expect(getIiifMaxNativeZoom(7392, 6270, 1024)).toBe(3);
  });

  it('builds CRS.Simple image bounds from pixel dimensions at native zoom', () => {
    const bounds = getIiifImageBounds(Leaflet, 7392, 6270, 3);

    expect(bounds.getSouthWest().lat).toBeCloseTo(-783.75);
    expect(bounds.getSouthWest().lng).toBeCloseTo(0);
    expect(bounds.getNorthEast().lat).toBeCloseTo(0);
    expect(bounds.getNorthEast().lng).toBeCloseTo(924);
  });

  it('pins IIIF maps to CRS.Simple and image bounds even when generic map settings exist', () => {
    const bounds = getIiifImageBounds(Leaflet, 7392, 6270, 3);
    const options = getIiifLeafletMapOptions(
      Leaflet,
      bounds,
      3,
      { SLEEP: false },
      {
        crs: Leaflet.CRS.EPSG3857,
        gestureHandling: true,
        maxZoom: 18,
        scrollWheelZoom: true,
        zoom: 7,
      }
    );

    expect(options.crs).toBe(Leaflet.CRS.Simple);
    expect(options.center.equals(bounds.getCenter())).toBe(true);
    expect(options.gestureHandling).toBe(true);
    expect(options.maxBounds.contains(bounds)).toBe(true);
    expect(options.maxZoom).toBe(3);
    expect(options.minZoom).toBe(IIIF_MIN_ZOOM);
    expect(options.scrollWheelZoom).toBe(true);
    expect(options.zoom).toBe(0);
  });

  it('allows large CONTENTdm scans to fit by zooming out below native IIIF zoom 0', () => {
    const maxNativeZoom = getIiifMaxNativeZoom(8826, 11246, 1024);
    const bounds = getIiifImageBounds(Leaflet, 8826, 11246, maxNativeZoom);
    const options = getIiifLeafletMapOptions(
      Leaflet,
      bounds,
      maxNativeZoom,
      { SLEEP: false },
      {}
    );

    expect(maxNativeZoom).toBe(4);
    expect(bounds.getNorthEast().lng).toBeCloseTo(551.625);
    expect(bounds.getSouthWest().lat).toBeCloseTo(-702.875);
    expect(options.minZoom).toBe(-5);
  });

  it('normalizes IIIF service ids from info.json metadata', () => {
    expect(
      normalizeIiifImageServiceId('https://example.com/fallback/info.json', {
        '@id': 'https://example.com/canonical/info.json',
      })
    ).toBe('https://example.com/canonical');
  });

  it('generates IIIF v2 region tile URLs for the initial zoom level', () => {
    expect(
      getIiifTileUrl({
        ...baseTileOptions,
        coords: { x: 0, y: 0, z: 0 },
      })
    ).toBe(
      'https://s3.amazonaws.com/ogm-metadata-studio/uploads/unr-74479f22-0e6b-4c13-b376-0195a7461525/iiif/0,0,7392,6270/924,/0/default.jpg'
    );
  });

  it('clamps display zooms below the native IIIF pyramid to zoom 0 tile requests', () => {
    expect(
      getIiifTileUrl({
        ...baseTileOptions,
        coords: { x: 0, y: 0, z: -2 },
      })
    ).toBe(
      getIiifTileUrl({
        ...baseTileOptions,
        coords: { x: 0, y: 0, z: 0 },
      })
    );
  });

  it('clips IIIF edge tiles to the image dimensions', () => {
    expect(
      getIiifTileUrl({
        ...baseTileOptions,
        coords: { x: 7, y: 6, z: 3 },
      })
    ).toBe(
      'https://s3.amazonaws.com/ogm-metadata-studio/uploads/unr-74479f22-0e6b-4c13-b376-0195a7461525/iiif/7168,6144,224,126/224,/0/default.jpg'
    );
  });

  it('uses IIIF v3 width,height size syntax', () => {
    expect(
      getIiifTileUrl({
        ...baseTileOptions,
        imageApiVersion: 3,
        coords: { x: 0, y: 0, z: 3 },
      })
    ).toBe(
      'https://s3.amazonaws.com/ogm-metadata-studio/uploads/unr-74479f22-0e6b-4c13-b376-0195a7461525/iiif/0,0,1024,1024/1024,1024/0/default.jpg'
    );
  });

  it('does not request remote URLs for tiles outside the image', () => {
    expect(
      getIiifTileUrl({
        ...baseTileOptions,
        coords: { x: 8, y: 0, z: 3 },
      })
    ).toBe(EMPTY_IIIF_TILE_URL);
  });

  it('resizes non-square IIIF tiles to their natural image dimensions', () => {
    const tile = document.createElement('img');
    Object.defineProperty(tile, 'naturalWidth', { value: 552 });
    Object.defineProperty(tile, 'naturalHeight', { value: 703 });

    resizeIiifTileToNaturalSize(tile, 1024);

    expect(tile.style.width).toBe('552px');
    expect(tile.style.height).toBe('703px');
  });

  it('leaves full-size square IIIF tiles alone', () => {
    const tile = document.createElement('img');
    Object.defineProperty(tile, 'naturalWidth', { value: 1024 });
    Object.defineProperty(tile, 'naturalHeight', { value: 1024 });

    resizeIiifTileToNaturalSize(tile, 1024);

    expect(tile.style.width).toBe('');
    expect(tile.style.height).toBe('');
  });
});
