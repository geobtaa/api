import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const fitInternal = vi.fn();
  const fit = vi.fn();
  const setCenter = vi.fn();
  const setResolution = vi.fn();
  const setViewportSize = vi.fn();
  const useGeographic = vi.fn();
  const transformExtent = vi.fn((extent: number[]) => extent);
  const geoTiff = vi.fn();
  const pmtilesVectorSource = vi.fn();
  const vectorTileLayer = vi.fn();
  const webglTileLayer = vi.fn();
  const tileLayer = vi.fn();
  const xyzSource = vi.fn();
  const style = vi.fn();
  const stroke = vi.fn();
  const fill = vi.fn();
  const circle = vi.fn();
  const polygonFromExtent = vi.fn((extent: number[]) => ({
    extent,
    getFlatCoordinates: () => extent,
    getStride: () => 2,
  }));
  const overlaySource = {
    getState: vi.fn(() => 'ready'),
    on: vi.fn(),
    un: vi.fn(),
  };
  const overlay = {
    getSource: vi.fn(() => overlaySource),
  };
  const map = {
    getSize: vi.fn(() => undefined),
    updateSize: vi.fn(),
    renderSync: vi.fn(),
    on: vi.fn(),
    setTarget: vi.fn(),
    getEventPixel: vi.fn(() => [0, 0]),
    hasFeatureAtPixel: vi.fn(() => false),
    getViewport: vi.fn(() => ({ style: { cursor: '' } })),
    getFeaturesAtPixel: vi.fn(() => []),
  };
  const view = {
    getProjection: vi.fn(() => ({ getCode: () => 'EPSG:3857' })),
    setViewportSize,
    fitInternal,
    fit,
    getCenterInternal: vi.fn(() => [-10381844.95, 5616966.0]),
    getCenter: vi.fn(() => [-10381844.95, 5616966.0]),
    setCenter,
    setResolution,
    getResolutionForExtentInternal: vi.fn(() => 128),
  };
  const olMap = vi.fn(() => map);
  const olView = vi.fn(() => view);

  vectorTileLayer.mockImplementation(() => overlay);
  webglTileLayer.mockImplementation(() => overlay);

  return {
    circle,
    fill,
    fit,
    fitInternal,
    geoTiff,
    map,
    olMap,
    olView,
    overlay,
    overlaySource,
    pmtilesVectorSource,
    polygonFromExtent,
    setCenter,
    setResolution,
    setViewportSize,
    stroke,
    style,
    tileLayer,
    transformExtent,
    useGeographic,
    vectorTileLayer,
    view,
    webglTileLayer,
    xyzSource,
  };
});

vi.mock('ol/Map', () => ({
  default: mocks.olMap,
}));

vi.mock('ol/View', () => ({
  default: mocks.olView,
}));

vi.mock('ol/control', () => ({
  FullScreen: vi.fn(function FullScreen() {}),
  defaults: vi.fn(() => ({
    extend: vi.fn(() => []),
  })),
}));

vi.mock('ol/layer/Tile', () => ({
  default: mocks.tileLayer,
}));

vi.mock('ol/source/XYZ', () => ({
  default: mocks.xyzSource,
}));

vi.mock('ol/layer/VectorTile.js', () => ({
  default: mocks.vectorTileLayer,
}));

vi.mock('ol/layer/WebGLTile.js', () => ({
  default: mocks.webglTileLayer,
}));

vi.mock('ol/source/GeoTIFF.js', () => ({
  default: mocks.geoTiff,
}));

vi.mock('ol-pmtiles', () => ({
  PMTilesVectorSource: mocks.pmtilesVectorSource,
}));

vi.mock('ol/style.js', () => ({
  Circle: mocks.circle,
  Fill: mocks.fill,
  Stroke: mocks.stroke,
  Style: mocks.style,
}));

vi.mock('ol/geom/Polygon', () => ({
  fromExtent: mocks.polygonFromExtent,
}));

vi.mock('ol/proj', () => ({
  transformExtent: mocks.transformExtent,
  useGeographic: mocks.useGeographic,
}));

import { ResourceViewer } from '../../../components/resource/ResourceViewer';

const cogDataWithGeometry = {
  attributes: { dct_references_s: {} },
  meta: {
    ui: {
      viewer: {
        protocol: 'cog',
        endpoint: 'https://example.com/cog.tif',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-97.73743, 30.28753],
              [-97.73743, 30.28409],
              [-97.73346, 30.28409],
              [-97.73346, 30.28753],
              [-97.73743, 30.28753],
            ],
          ],
        },
      },
    },
  },
} as Parameters<typeof ResourceViewer>[0]['data'];

const pmtilesDataWithGeometry = {
  attributes: { dct_references_s: {} },
  meta: {
    ui: {
      viewer: {
        protocol: 'pmtiles',
        endpoint: 'https://example.com/test.pmtiles',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-93.3291, 44.8908],
              [-93.3291, 45.0512],
              [-93.1943, 45.0512],
              [-93.1943, 44.8908],
              [-93.3291, 44.8908],
            ],
          ],
        },
      },
    },
  },
} as Parameters<typeof ResourceViewer>[0]['data'];

const wmsDataWithGeometry = {
  attributes: {
    dct_references_s: {},
    ogm: {
      id: 'cook-county-contours',
      gbl_wxsIdentifier_s: 'Contours',
    },
  },
  meta: {
    ui: {
      viewer: {
        protocol: 'wms',
        endpoint:
          'https://example.com/cook-county/services/contours/MapServer/WMSServer',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-88.2, 41.6],
              [-88.2, 42.2],
              [-87.4, 42.2],
              [-87.4, 41.6],
              [-88.2, 41.6],
            ],
          ],
        },
      },
    },
  },
} as Parameters<typeof ResourceViewer>[0]['data'];

const secondWmsDataWithGeometry = {
  attributes: {
    dct_references_s: {},
    ogm: {
      id: 'cook-county-zoning',
      gbl_wxsIdentifier_s: 'Zoning',
    },
  },
  meta: {
    ui: {
      viewer: {
        protocol: 'wms',
        endpoint:
          'https://example.com/cook-county/services/zoning/MapServer/WMSServer',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-88.0, 41.7],
              [-88.0, 42.0],
              [-87.5, 42.0],
              [-87.5, 41.7],
              [-88.0, 41.7],
            ],
          ],
        },
      },
    },
  },
} as Parameters<typeof ResourceViewer>[0]['data'];

describe('ResourceViewer', () => {
  let rectSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    vi.stubGlobal(
      'ResizeObserver',
      class ResizeObserver {
        observe = vi.fn();
        disconnect = vi.fn();
      }
    );
    rectSpy = vi
      .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockReturnValue({
        width: 1094,
        height: 600,
        top: 0,
        left: 0,
        right: 1094,
        bottom: 600,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      } as DOMRect);
  });

  afterEach(() => {
    rectSpy.mockRestore();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    mocks.map.getSize.mockReturnValue(undefined);
    mocks.view.getCenterInternal.mockReturnValue([-10381844.95, 5616966.0]);
    mocks.overlaySource.getState.mockReturnValue('ready');
  });

  describe('OpenLayers viewer bootstrap', () => {
    it('fits a COG map using the rendered element size when map size is unavailable', async () => {
      render(<ResourceViewer data={cogDataWithGeometry} pageValue="SHOW" />);

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(mocks.olMap).toHaveBeenCalled();
      expect(mocks.geoTiff).toHaveBeenCalledWith({
        sources: [{ url: 'https://example.com/cog.tif' }],
        convertToRGB: true,
      });
      expect(mocks.setViewportSize).toHaveBeenCalledWith([1094, 600]);
      expect(mocks.fitInternal).toHaveBeenCalled();
      expect(mocks.fitInternal.mock.calls[0][1]).toMatchObject({
        size: [1094, 600],
        maxZoom: 19,
      });
    });

    it('boots PMTiles through the local layer path and enables geographic mode', async () => {
      render(
        <ResourceViewer data={pmtilesDataWithGeometry} pageValue="SHOW" />
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(mocks.useGeographic).toHaveBeenCalled();
      expect(mocks.pmtilesVectorSource).toHaveBeenCalledWith({
        url: 'https://example.com/test.pmtiles',
      });
      expect(mocks.vectorTileLayer).toHaveBeenCalled();
      expect(mocks.fitInternal).toHaveBeenCalled();
    });
  });

  describe('Leaflet-backed viewer remounts', () => {
    it('replaces the viewer container when the resource changes', async () => {
      const { rerender, container } = render(
        <ResourceViewer data={wmsDataWithGeometry} pageValue="SHOW" />
      );

      await act(async () => {});

      const firstViewer = container.querySelector('#leaflet-viewer');
      expect(firstViewer).not.toBeNull();
      expect(
        firstViewer?.getAttribute('data-leaflet-viewer-layer-id-value')
      ).toBe('Contours');

      rerender(
        <ResourceViewer data={secondWmsDataWithGeometry} pageValue="SHOW" />
      );

      await act(async () => {});

      const secondViewer = container.querySelector('#leaflet-viewer');
      expect(secondViewer).not.toBeNull();
      expect(secondViewer).not.toBe(firstViewer);
      expect(
        secondViewer?.getAttribute('data-leaflet-viewer-layer-id-value')
      ).toBe('Zoning');
      expect(secondViewer?.getAttribute('data-leaflet-viewer-url-value')).toBe(
        'https://example.com/cook-county/services/zoning/MapServer/WMSServer'
      );
    });
  });
});
