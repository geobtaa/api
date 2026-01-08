import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { SearchPage } from '../../pages/SearchPage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { vi } from 'vitest';

vi.mock('../../components/search/GeospatialFilterMap', () => ({
  GeospatialFilterMap: () => (
    <button type="button" aria-label="zoom in">
      Zoom in
    </button>
  ),
}));

vi.mock('../../hooks/useSearch', () => ({
  useSearch: () => ({
    query: '',
    results: null,
    isLoading: false,
    error: null,
    page: 1,
    perPage: 10,
    totalResults: 0,
    facets: [],
    excludeFacets: [],
    advancedQuery: [],
    sort: 'relevance',
    updateSearch: vi.fn(),
  }),
}));

describe('Search Results Page', () => {
  const renderSearchResults = (initialEntry: string = '/search') => {
    render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <ApiProvider>
          <DebugProvider>
            <SearchPage searchResults={null} isLoading={false} />
          </DebugProvider>
        </ApiProvider>
      </MemoryRouter>
    );
  };

  it('displays search results', async () => {
    renderSearchResults();
    await waitFor(() => {
      expect(screen.getByRole('main')).toBeInTheDocument();
    });
  });

  it('shows the map view', () => {
    renderSearchResults();
    // The map is always visible on large screens, check for map container
    expect(screen.getAllByRole('button', { name: /zoom in/i }).length).toBeGreaterThan(0);
  });

  it('shows “Searching…” placeholder before results are available (instead of 0-0 of 0)', () => {
    renderSearchResults('/search?q=');
    expect(screen.getByText(/Searching/)).toBeInTheDocument();
    expect(screen.queryByText(/Showing results/i)).not.toBeInTheDocument();
  });
});
