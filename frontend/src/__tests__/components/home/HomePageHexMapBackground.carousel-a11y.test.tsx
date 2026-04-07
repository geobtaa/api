/**
 * Accessibility tests for the Featured resources carousel on the homepage.
 * Mocks map/Leaflet so the carousel UI renders and can be tested with axe.
 */
import { render, screen } from '@testing-library/react';
import { axeWithWCAG22 } from '../../../test-utils/axe';
import { BrowserRouter } from 'react-router';
import { vi } from 'vitest';
import { HomePageHexMapBackground } from '../../../components/home/HomePageHexMapBackground.client';

vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('leaflet-gesture-handling', () => ({ GestureHandling: {} }));

vi.mock('../../../components/map/BasemapSwitcherControl', () => ({
  BasemapSwitcherControl: () => null,
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

const mockNavigate = vi.fn();
vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('HomePageHexMapBackground – Featured carousel accessibility', () => {
  it('has no accessibility violations in carousel region', async () => {
    render(
      <BrowserRouter>
        <HomePageHexMapBackground />
      </BrowserRouter>
    );

    const carousel = screen.getByRole('region', {
      name: /Featured resources/i,
    });
    expect(carousel).toBeInTheDocument();

    const results = await axeWithWCAG22(carousel);
    expect(results).toHaveNoViolations();
  });

  it('carousel has roledescription and description', () => {
    render(
      <BrowserRouter>
        <HomePageHexMapBackground />
      </BrowserRouter>
    );

    const carousel = screen.getByRole('region', {
      name: /Featured resources/i,
    });
    expect(carousel).toHaveAttribute('aria-roledescription', 'carousel');
    expect(carousel).toHaveAttribute(
      'aria-describedby',
      'featured-carousel-desc'
    );
    expect(document.getElementById('featured-carousel-desc')).toHaveTextContent(
      /Use previous and next buttons/i
    );
  });
});
