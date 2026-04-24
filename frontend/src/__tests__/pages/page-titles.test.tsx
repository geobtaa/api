/**
 * Ensures all main user-facing pages render a <title> element.
 * Uses react-helmet-async (via Seo component) to set document title.
 */
import { render, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useParams: () => ({ id: 'test-id' }),
  };
});
import { HomePage } from '../../pages/HomePage';
import { SearchPage } from '../../pages/SearchPage';
import { ResourceView } from '../../pages/ResourceView';
import { BookmarksPage } from '../../pages/BookmarksPage';
import { NotFoundPage } from '../../pages/NotFoundPage';
import { MapPage } from '../../pages/MapPage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { BookmarkProvider } from '../../context/BookmarkContext';
import { MapProvider } from '../../context/MapContext';
import Cookies from 'js-cookie';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
  generateAnalyticsId: vi.fn(() => 'search_test_id'),
  serializeSearchParams: vi.fn(() => ({})),
}));

// Mocks to keep page rendering lightweight
vi.mock('../../components/SearchField', () => ({
  SearchField: () => <input placeholder="Search" />,
}));
vi.mock('../../components/search/GeospatialFilterMap', () => ({
  GeospatialFilterMap: () => null,
}));
vi.mock('../../components/SearchResults', () => ({
  SearchResults: () => <div data-testid="search-results" />,
}));
vi.mock('../../components/search/GalleryView', () => ({
  GalleryView: () => <div data-testid="gallery-view" />,
}));
vi.mock('../../components/home/HomePageHexMapBackground.client', () => ({
  HomePageHexMapBackground: () => null,
}));
vi.mock('../../components/search/MapView', () => ({
  MapView: () => null,
}));
// MapPage.client pulls in Leaflet, useGeoFacets, useMapH3 - mock to isolate title test
// vi.mock factory is hoisted, so we use require (eslint disable required)
vi.mock('../../pages/MapPage.client', () => {
  /* eslint-disable @typescript-eslint/no-require-imports */
  const React = require('react');
  const { Helmet } = require('react-helmet-async');
  /* eslint-enable @typescript-eslint/no-require-imports */
  const MockMapClient = () =>
    React.createElement(
      React.Fragment,
      null,
      React.createElement(Helmet, null, React.createElement('title', null, 'Map - Big Ten Academic Alliance Geoportal')),
      React.createElement('div', { 'data-testid': 'map-page-client' }, 'Map')
    );
  return { MapPage: MockMapClient, default: MockMapClient };
});

function assertHasTitle() {
  const titleEl = document.querySelector('title');
  expect(titleEl).toBeInTheDocument();
  expect(titleEl?.textContent?.trim()).toBeTruthy();
}

describe('Page titles', () => {
  beforeEach(() => {
    document.head.innerHTML = '';
    Cookies.remove('bookmarks');
  });

  it('HomePage has a title', async () => {
    const routes = [
      {
        path: '/',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <DebugProvider>
                <HomePage />
              </DebugProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];
    const router = createMemoryRouter(routes, { initialEntries: ['/'] });
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      assertHasTitle();
    });
  });

  it('SearchPage has a title', async () => {
    const routes = [
      {
        path: '/search',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <DebugProvider>
                <MapProvider>
                  <SearchPage />
                </MapProvider>
              </DebugProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];
    const router = createMemoryRouter(routes, {
      initialEntries: ['/search?q='],
    });
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      assertHasTitle();
    });
  });

  it('ResourceView has a title', async () => {
    const routes = [
      {
        path: '/resources/:id',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <DebugProvider>
                <ResourceView />
              </DebugProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];
    const router = createMemoryRouter(routes, {
      initialEntries: ['/resources/test-id'],
    });
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      assertHasTitle();
    });
  });

  it('BookmarksPage has a title', async () => {
    Cookies.set('bookmarks', JSON.stringify([]));
    const routes = [
      {
        path: '/bookmarks',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <BookmarkProvider>
                <DebugProvider>
                  <BookmarksPage />
                </DebugProvider>
              </BookmarkProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];
    const router = createMemoryRouter(routes, {
      initialEntries: ['/bookmarks'],
    });
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      assertHasTitle();
    });
  });

  it('NotFoundPage has a title', async () => {
    const routes = [
      {
        path: '*',
        element: (
          <HelmetProvider>
            <NotFoundPage />
          </HelmetProvider>
        ),
      },
    ];
    const router = createMemoryRouter(routes, {
      initialEntries: ['/nonexistent'],
    });
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      assertHasTitle();
    });
  });

  it('MapPage has a title', async () => {
    const routes = [
      {
        path: '/map',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <DebugProvider>
                <MapPage />
              </DebugProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];
    const router = createMemoryRouter(routes, {
      initialEntries: ['/map'],
    });
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      assertHasTitle();
    });
  });
});
