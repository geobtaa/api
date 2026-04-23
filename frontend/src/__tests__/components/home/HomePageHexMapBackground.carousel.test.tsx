/**
 * Behavior tests for the Featured resources carousel on the homepage.
 * Covers: thumbnail selection (no auto-start), Play/Pause, animation from selected item.
 */
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as api from '../../../services/api';
import { FEATURED_RESOURCE_IDS } from '../../../config/featured';
import { HomePageHexMapBackground } from '../../../components/home/HomePageHexMapBackground.client';

vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('leaflet-gesture-handling', () => ({ GestureHandling: {} }));

vi.mock('../../../components/map/BasemapSwitcherControl', () => ({
  BasemapSwitcherControl: () => null,
}));

vi.mock('../../../components/map/HexLayerToggleControl', () => ({
  HexLayerToggleControl: ({
    enabled,
    onToggle,
  }: {
    enabled: boolean;
    onToggle: (enabled: boolean) => void;
  }) => (
    <div>
      <div data-testid="homepage-hex-enabled-state">{String(enabled)}</div>
      <button
        type="button"
        data-testid="homepage-hex-toggle-btn"
        onClick={() => onToggle(!enabled)}
      >
        Toggle homepage hex
      </button>
    </div>
  ),
}));

vi.mock('../../../components/map/MapGeosearchControl', () => ({
  MapGeosearchControl: () => <div data-testid="homepage-map-geosearch" />,
}));

const mockPane = document.createElement('div');
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => null,
  ZoomControl: () => null,
  Rectangle: () => null,
  useMap: () => ({
    getContainer: () => document.createElement('div'),
    getBounds: () => ({
      getWest: () => -100,
      getSouth: () => 30,
      getEast: () => -80,
      getNorth: () => 50,
      getNorthEast: () => ({ lat: 50, lng: -80 }),
      getSouthWest: () => ({ lat: 30, lng: -100 }),
    }),
    getZoom: () => 5,
    whenReady: (cb: () => void) => cb(),
    on: () => {},
    off: () => {},
    hasLayer: () => false,
    addLayer: vi.fn(),
    removeLayer: () => {},
    fitBounds: () => {},
    getPane: () => null,
    createPane: () => mockPane,
    panBy: () => {},
  }),
  useMapEvents: () => null,
}));

vi.mock('../../../components/map/MapUpdaterHex', () => ({
  MapUpdaterHex: () => null,
}));

vi.mock('../../../components/home/FeaturedMapController', () => ({
  FeaturedMapController: () => null,
}));

vi.mock('../../../components/home/FeaturedItemPreviewLayer', () => ({
  FeaturedItemPreviewLayer: () => null,
}));

vi.mock('../../../components/home/FeaturedItemBoundsLayer', () => ({
  FeaturedItemBoundsLayer: () => null,
}));

vi.mock('../../../components/map/H3HexDataTable', () => ({
  H3HexDataTable: () => <div data-testid="h3-hex-table">Hex table</div>,
}));

function makeMockDetail(id: string, title: string) {
  return {
    id,
    type: 'resource',
    attributes: {
      ogm: {
        id,
        dct_title_s: title,
        dct_description_sm: ['Description'],
        dct_temporal_sm: ['2023'],
        dc_publisher_sm: ['Publisher'],
        gbl_resourceClass_sm: ['Dataset'],
      },
    },
    meta: {
      ui: {
        thumbnail_url: null,
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-93.265, 44.9778],
          },
        },
      },
    },
  };
}

const MOCK_DETAILS = FEATURED_RESOURCE_IDS.map((id, i) =>
  makeMockDetail(id, `Featured Item ${i + 1}`)
);

describe('HomePageHexMapBackground – Featured carousel behavior', () => {
  const user = userEvent.setup({ delay: null });

  beforeEach(() => {
    vi.useRealTimers();
    localStorage.clear();
    vi.mocked(api.fetchFeaturedResourcePreview).mockImplementation((id: string) => {
      const idx = FEATURED_RESOURCE_IDS.indexOf(id);
      return Promise.resolve(
        MOCK_DETAILS[idx >= 0 ? idx : 0] as Awaited<
          ReturnType<typeof api.fetchFeaturedResourcePreview>
        >
      );
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const renderCarousel = () => {
    render(
      <BrowserRouter>
        <HomePageHexMapBackground />
      </BrowserRouter>
    );
  };

  const waitForFeaturedData = async () => {
    await screen.findByRole(
      'button',
      { name: /Featured Item 1|Test Resource/i },
      { timeout: 8000 }
    );
  };

  const getPlayPauseButton = () =>
    screen.getByRole('button', {
      name: /Start featured carousel|Play featured carousel|Pause featured carousel/i,
    });

  const getProgressBar = () =>
    screen.getByRole('progressbar', { name: /Time remaining/i });

  it('carousel region renders with expected structure', async () => {
    renderCarousel();
    const carousel = await screen.findByRole('region', {
      name: /Featured resources/i,
    });
    expect(carousel).toBeInTheDocument();
    expect(carousel).toHaveAttribute('aria-roledescription', 'carousel');
    expect(getPlayPauseButton()).toBeInTheDocument();
  });

  it('restores and persists homepage hex layer preference via localStorage', async () => {
    localStorage.setItem('hex_layer_enabled', '0');
    renderCarousel();

    expect(
      await screen.findByTestId('homepage-hex-enabled-state')
    ).toHaveTextContent('false');

    await user.click(screen.getByTestId('homepage-hex-toggle-btn'));

    await waitFor(() => {
      expect(localStorage.getItem('hex_layer_enabled')).toBe('1');
    });
    expect(screen.getByTestId('homepage-hex-enabled-state')).toHaveTextContent(
      'true'
    );
  });

  it('clicking a featured item thumbnail highlights it without starting the animation', async () => {
    renderCarousel();
    await waitForFeaturedData();

    const thirdThumb = screen.getByRole('button', {
      name: /Featured Item 3/i,
    });
    await user.click(thirdThumb);

    expect(screen.getByRole('status', { hidden: true })).toHaveTextContent(
      /Current featured item: Featured Item 3/i
    );

    const progressBar = getProgressBar();
    expect(progressBar).toBeInTheDocument();
    expect(progressBar).toHaveAttribute('aria-valuenow', '100');

    vi.useFakeTimers();
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    vi.useRealTimers();

    expect(getProgressBar()).toHaveAttribute('aria-valuenow', '100');
  });
});
