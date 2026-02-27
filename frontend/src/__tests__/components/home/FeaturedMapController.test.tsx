import { render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import L from 'leaflet';
import { FeaturedMapController } from '../../../components/home/FeaturedMapController';
import { HOME_PAGE_MAP_CENTER, DEFAULT_US_ZOOM } from '../../../config/mapView';

const mockMap = {
  flyTo: vi.fn(),
  flyToBounds: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  getBoundsZoom: vi.fn(() => 2),
  project: vi.fn(() => L.point(100, 200)),
  unproject: vi.fn(() => L.latLng(15, 25)),
  getMaxZoom: vi.fn(() => 18),
};

vi.mock('react-leaflet', () => ({
  useMap: () => mockMap,
}));

vi.mock('../../../components/home/FeaturedItemPreviewLayer', () => ({
  hasAllmapsViewer: () => false,
}));

function makeDetail({
  bbox = 'ENVELOPE(-10,10,50,30)',
  allmaps = false,
}: {
  bbox?: string;
  allmaps?: boolean;
}) {
  return {
    id: 'item-1',
    type: 'resource',
    attributes: {
      ogm: {
        dcat_bbox: bbox,
      },
    },
    meta: {
      ui: allmaps
        ? {
            allmaps: {
              allmaps_annotated: true,
              allmaps_annotation_url: 'https://annotations.allmaps.org/abc',
            },
          }
        : {},
    },
  } as any;
}

describe('FeaturedMapController camera precedence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses explicit center+zoom override before bbox fit', () => {
    render(
      <FeaturedMapController
        activeIndex={0}
        featuredDetails={[makeDetail({})]}
        featuredCamera={{ mode: 'flyTo', center: [40, -90], zoom: 6 }}
        featuredInitiated
        programmaticFlyRef={{ current: false }}
      />
    );

    expect(mockMap.flyTo).toHaveBeenCalledTimes(1);
    expect(mockMap.flyToBounds).not.toHaveBeenCalled();
    expect(mockMap.flyTo.mock.calls[0][1]).toBe(6);
  });

  it('falls back to fitBounds when no explicit override is supplied', () => {
    render(
      <FeaturedMapController
        activeIndex={0}
        featuredDetails={[makeDetail({})]}
        featuredInitiated
        programmaticFlyRef={{ current: false }}
      />
    );

    expect(mockMap.flyToBounds).toHaveBeenCalledTimes(1);
    expect(mockMap.flyTo).not.toHaveBeenCalled();
    expect(mockMap.flyToBounds.mock.calls[0][1]).toMatchObject({
      padding: [60, 60],
      maxZoom: 10,
      duration: 1.5,
    });
  });

  it('falls back to homepage default camera when bbox is invalid', () => {
    render(
      <FeaturedMapController
        activeIndex={0}
        featuredDetails={[makeDetail({ bbox: 'INVALID_BBOX' })]}
        featuredInitiated
        programmaticFlyRef={{ current: false }}
      />
    );

    expect(mockMap.flyTo).toHaveBeenCalledTimes(1);
    const flyArgs = mockMap.flyTo.mock.calls[0];
    expect(flyArgs[0]).toMatchObject({
      lat: HOME_PAGE_MAP_CENTER[0],
      lng: HOME_PAGE_MAP_CENTER[1],
    });
    expect(flyArgs[1]).toBe(DEFAULT_US_ZOOM);
  });

  it('derives zoom from bbox and respects minZoom/offset in flyTo mode', () => {
    render(
      <FeaturedMapController
        activeIndex={0}
        featuredDetails={[makeDetail({})]}
        featuredCamera={{ mode: 'flyTo', minZoom: 3, verticalOffsetPx: 40 }}
        featuredInitiated
        programmaticFlyRef={{ current: false }}
      />
    );

    expect(mockMap.getBoundsZoom).toHaveBeenCalled();
    expect(mockMap.project).toHaveBeenCalled();
    expect(mockMap.unproject).toHaveBeenCalled();
    expect(mockMap.flyTo).toHaveBeenCalledTimes(1);
    expect(mockMap.flyTo.mock.calls[0][1]).toBe(3);
  });
});
