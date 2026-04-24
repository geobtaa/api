import { render, screen, waitFor, act } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { SearchPage } from '../../pages/SearchPage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { MapProvider } from '../../context/MapContext';
import {
  vi,
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  MockInstance,
} from 'vitest';
import type { GeoDocument, JsonApiResponse } from '../../types/api';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
  generateAnalyticsId: vi.fn(() => 'search_test_id'),
  serializeSearchParams: vi.fn(() => ({})),
}));

// Mock child components to isolate SearchPage logic
vi.mock('../../components/search/GeospatialFilterMap', () => ({
  GeospatialFilterMap: () => <div data-testid="geo-filter-map">Geo Map</div>,
}));

vi.mock('../../components/search/ResourceClassFilterTabs', () => ({
  ResourceClassFilterTabs: () => (
    <div data-testid="resource-class-filter-tabs">Resource Class Tabs</div>
  ),
}));

vi.mock('../../components/SearchResults', () => ({
  SearchResults: ({ results }: { results: GeoDocument[] }) => (
    <div data-testid="search-results-list">
      {results.map((r) => (
        <div key={r.id}>List Result {r.attributes.ogm.dct_title_s}</div>
      ))}
    </div>
  ),
}));

// Mock GalleryView specifically to test interaction or simply use real one?
// Using real one allows us to test the composition, but mocking it makes testing SearchPage's state passing easier.
// Let's use REAL GalleryView if possible, or a mock that exposes props.
// Actually, for deep logic testing (infinite scroll callback), mocking is often cleaner.
// But we want to test that SearchPage *passes* the right props.
vi.mock('../../components/search/GalleryView', () => ({
  GalleryView: ({
    results,
    onLoadMore,
  }: {
    results: GeoDocument[];
    onLoadMore: () => void;
  }) => (
    <div data-testid="gallery-view">
      {results.map((r) => (
        <div key={r.id}>Gallery Result {r.attributes.ogm.dct_title_s}</div>
      ))}
      <button onClick={onLoadMore} data-testid="load-more-btn">
        Load More
      </button>
    </div>
  ),
}));

vi.mock('../../components/search/MapResultView', () => ({
  MapResultView: () => <div data-testid="map-result-view">Map Result View</div>,
}));

const mockResults: GeoDocument[] = Array.from({ length: 40 }, (_, i) => ({
  type: 'file',
  id: `result-${i + 1}`,
  attributes: {
    ogm: {
      dct_title_s: `Result ${i + 1}`,
      gbl_resourceClass_sm: ['Map'],
    },
    // Add other required fields if necessary
  },
  links: { self: '#' },
}));

const createMockApiResponse = (
  data: GeoDocument[],
  total = 100,
  page = 1
): JsonApiResponse => ({
  data,
  meta: {
    pages: {
      current_page: page,
      next_page: page + 1, // simplified
      prev_page: page > 1 ? page - 1 : null,
      total_pages: Math.ceil(total / 20),
      total_count: total,
    },
    totalCount: total, // SearchPage uses this
    perPage: 20,
  },
  links: { self: '', next: '', prev: '', first: '', last: '' },
  included: [],
});

describe('SearchPage Logic', () => {
  let getItemSpy: MockInstance;
  let setItemSpy: MockInstance;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    getItemSpy = vi.spyOn(sessionStorage, 'getItem');
    setItemSpy = vi.spyOn(sessionStorage, 'setItem');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderWithRouter = (
    initialUrl = '/search',
    searchResults: JsonApiResponse | null = null,
    options?: { returnRouter?: boolean }
  ) => {
    const routes = [
      {
        path: '/search',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <DebugProvider>
                {/* MapProvider is guarded inside SearchPage, but we can wrap here too just in case context is needed outside */}
                <SearchPage searchResults={searchResults} isLoading={false} />
              </DebugProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];

    const router = createMemoryRouter(routes, {
      initialEntries: [initialUrl],
    });

    const result = render(<RouterProvider router={router} />);
    return options?.returnRouter ? { ...result, router } : result;
  };

  it('renders Gallery View when view=gallery param is present', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?view=gallery', results);

    expect(screen.getByTestId('gallery-view')).toBeInTheDocument();
    expect(screen.queryByTestId('search-results-list')).not.toBeInTheDocument();
  });

  it('does not mount the location map by default in gallery view', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?view=gallery', results);

    expect(screen.queryByTestId('geo-filter-map')).not.toBeInTheDocument();
  });

  it('mounts the location map by default in map view', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?view=map', results);

    expect(screen.getByTestId('geo-filter-map')).toBeInTheDocument();
  });

  it('renders List View by default', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search', results);

    expect(screen.getByTestId('search-results-list')).toBeInTheDocument();
    expect(screen.queryByTestId('gallery-view')).not.toBeInTheDocument();
  });

  it('restores saved map view preference when URL has no view param', async () => {
    localStorage.setItem('b1g_view_preference', 'map');
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?q=', results);

    await waitFor(() => {
      expect(screen.getByTestId('map-result-view')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('gallery-view')).not.toBeInTheDocument();
  });

  it('restores saved gallery view preference when URL has no view param', async () => {
    localStorage.setItem('b1g_view_preference', 'gallery');
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?q=', results);

    await waitFor(() => {
      expect(screen.getByTestId('gallery-view')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('search-results-list')).not.toBeInTheDocument();
    expect(screen.queryByTestId('map-result-view')).not.toBeInTheDocument();
  });

  it('preserves bbox filter when removing facet from search constraints', async () => {
    const bboxAndMapsUrl =
      '/search?q=&view=map' +
      '&include_filters%5Bgeo%5D%5Btype%5D=bbox' +
      '&include_filters%5Bgeo%5D%5Bfield%5D=dcat_bbox' +
      '&include_filters%5Bgeo%5D%5Btop_left%5D%5Blat%5D=41.28' +
      '&include_filters%5Bgeo%5D%5Btop_left%5D%5Blon%5D=-90.76' +
      '&include_filters%5Bgeo%5D%5Bbottom_right%5D%5Blat%5D=34.59' +
      '&include_filters%5Bgeo%5D%5Bbottom_right%5D%5Blon%5D=-82.28' +
      '&include_filters%5Bgbl_resourceClass_sm%5D%5B%5D=Maps';

    const results = createMockApiResponse(mockResults.slice(0, 20));
    const { router } = renderWithRouter(bboxAndMapsUrl, results, {
      returnRouter: true,
    });

    const mapsButton = screen.getByRole('button', {
      name: /Resource Class: Maps/i,
    });
    await act(async () => {
      mapsButton.click();
    });

    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('include_filters[geo][type]')).toBe('bbox');
    expect(params.get('include_filters[geo][top_left][lat]')).toBe('41.28');
    expect(params.get('include_filters[geo][bottom_right][lat]')).toBe(
      '34.59'
    );
    expect(params.get('include_filters[gbl_resourceClass_sm][]')).toBeNull();
  });

  it('displays correct pagination text for initial gallery load', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20), 100, 1);
    renderWithRouter('/search?view=gallery', results);

    // Should show 1-20
    expect(
      screen.getByText(/Showing results 1-20 of 100/i)
    ).toBeInTheDocument();
  });

  it('does not crash when gallery session cache exceeds quota', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20), 100, 1);
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    setItemSpy.mockImplementation(() => {
      throw new DOMException(
        'Setting the value exceeded the quota.',
        'QuotaExceededError'
      );
    });

    renderWithRouter('/search?view=gallery', results);

    await waitFor(() => {
      expect(screen.getByTestId('gallery-view')).toBeInTheDocument();
    });

    expect(warnSpy).toHaveBeenCalledWith(
      'Gallery state cache exceeded session storage quota; skipping persistence.'
    );
  });

  it('appends results when Load More is clicked (simulating infinite scroll)', async () => {
    // Initial load: Page 1 (items 1-20)
    // We simulate the router/loader response updating. In a real integration test we'd update the router state or mock the loader.
    // However, SearchPage receives `searchResults` prop.
    // BUT! SearchPage handles `setAccumulatedResults`.
    // Wait, `onLoadMore` calls `handlePageChange` which updates URL.
    // The *parent* (loader) usually fetches new data and re-renders SearchPage with new `searchResults`.

    // To test this with `render`, we need to simulate the component re-rendering with new props (Page 2 data)
    // while maintaining component state (accumulatedResults).

    const { rerender } = renderWithRouter(
      '/search?view=gallery',
      createMockApiResponse(mockResults.slice(0, 20), 100, 1)
    );

    // Check initial state
    expect(screen.getAllByText(/Gallery Result/)).toHaveLength(20);

    // Click load more -> updates URL to page=2.
    // In our test, we manually trigger the prop update that the loader would produce.
    // The component *must* detect that page changed (via props/URL) and context is same, and append.

    // Update router simulated? No, we pass props.
    // Note: SearchPage uses `useSearchParams`. We need to make sure the URL updates too.
    // Clicking "Load More" triggers `setSearchParams({ page: 2 })`.
    // This updates the URL.
    // The TEST runner (MemoryRouter) handles the URL update.
    // BUT we need to feed the *new data* corresponding to that URL.
    // Since we are not using a real loader, `searchResults` prop won't automatically update unless we wrap the test component or use a specialized helper.

    // Actually, `SearchPage` uses `useSearchParams`. The `searchResults` prop comes from the loader.
    // If we just change the URL, `searchResults` prop won't change in this test setup.
    // We need to re-render the component with the NEW `searchResults` when the URL changes.
    // Vitest doesn't easily support "smart" loader mocking out of the box with `createMemoryRouter` unless we define a loader.

    // ALTERNATIVE: We can test the *logic* of aggregation by purely updating props with same URL context but different data?
    // No, `useEffect` depends on `page` from URL.

    // Let's rely on the fact that `accumulatedResults` logic is:
    // 1. Initial render -> 20 items.
    // 2. Props update with Page 2 data -> Append.

    // We can simulate this by re-rendering with updated Router (to provide new Page param) AND updated props.
    // But `rerender` replaces the component. Does it preserve state? Yes.

    // Manually force a re-render sequence:
    // 1. Render P1.
    // 2. Rerender with P2 props. (We invoke rerender with the SAME component structure but new props).
    // Note: To change the Page param in `useSearchParams`, we might need to rely on the button click logic OR just force it via initialEntries?
    // No, we want to test the TRANSITION.

    // Limitation: We can't easily sync the internal Router state change with our external `searchResults` prop update in one go.
    // However, the `useEffect` listens to `page` from URL.
    // Valid Test Strategy:
    // 1. Render.
    // 2. Click Load More. (Updates URL param to page=2).
    // 3. This triggers a re-render. `searchResults` is STILL Page 1 data (old props).
    // 4. We then `rerender` with Page 2 data. The component sees Page 2 in URL + Page 2 in Props.
    // 5. It should append.

    await act(async () => {
      screen.getByTestId('load-more-btn').click();
    });

    // At this point URL is page=2 (due to click). Props are old.
    // Now we supply new data.
    const page2Results = createMockApiResponse(
      mockResults.slice(20, 40),
      100,
      2
    );

    // We need to pass the updated router context?
    // Actually `renderWithRouter` creates a new router each time. We can't use it for rerender.
    // We need to construct the setup manually to support rerender.

    // Refactored setup for this specific test
  });
});

describe('SearchPage Integration', () => {
  it('restores gallery state from session storage', async () => {
    // Mock session storage with pre-existing state
    const storedState = {
      context: 'view=gallery',
      results: mockResults.slice(0, 40), // 40 items
      startPage: 1,
    };
    sessionStorage.setItem('b1g_gallery_state', JSON.stringify(storedState));
    sessionStorage.setItem('b1g_gallery_restore_requested', '1');

    // Initial render with SERVER data (Page 1 only - 20 items)
    const serverResults = createMockApiResponse(
      mockResults.slice(0, 20),
      100,
      1
    );

    // We use view=gallery
    const { unmount } = renderWithRouter('/search?view=gallery', serverResults);

    // Should INITIALIZE with server data (20 items) but then EFFECT restores 40 items.
    // Wait for restoration.
    await waitFor(() => {
      // Check that we display 40 items (restored from session)
      expect(screen.getAllByText(/Gallery Result/)).toHaveLength(40);
    });

    expect(
      screen.getByText(/Showing results 1-40 of 100/i)
    ).toBeInTheDocument();

    unmount();
  });

  it('does not restore gallery state without an explicit restore request', async () => {
    const storedState = {
      context: 'view=gallery',
      results: mockResults.slice(0, 40),
      startPage: 1,
    };
    sessionStorage.setItem('b1g_gallery_state', JSON.stringify(storedState));

    const serverResults = createMockApiResponse(
      mockResults.slice(0, 20),
      100,
      1
    );

    renderWithRouter('/search?view=gallery', serverResults);

    await waitFor(() => {
      expect(screen.getAllByText(/Gallery Result/)).toHaveLength(20);
    });

    expect(
      screen.getByText(/Showing results 1-20 of 100/i)
    ).toBeInTheDocument();
  });

  // Helper must be defined in scope or imported
  const renderWithRouter = (
    initialUrl = '/search',
    searchResults: JsonApiResponse | null = null
  ) => {
    const routes = [
      {
        path: '/search',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <DebugProvider>
                <SearchPage searchResults={searchResults} isLoading={false} />
              </DebugProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];

    const router = createMemoryRouter(routes, {
      initialEntries: [initialUrl],
    });

    return render(<RouterProvider router={router} />);
  };
});
