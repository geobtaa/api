import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  act,
} from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { SearchField } from '../../components/SearchField';

const fetchNominatimSearchMock = vi.fn();

vi.mock('../../services/api', () => ({
  fetchNominatimSearch: (...args: unknown[]) =>
    fetchNominatimSearchMock(...args),
}));

function LocationProbe() {
  const location = useLocation();
  return (
    <div
      data-testid="location-probe"
      data-pathname={location.pathname}
      data-search={location.search}
    />
  );
}

describe('SearchField', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      json: async () => ({ data: [] }),
    }) as unknown as typeof fetch;

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        media: '',
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it('defaults header place bbox searches to overlap', async () => {
    fetchNominatimSearchMock.mockResolvedValue({
      data: [
        {
          id: 'illinois',
          type: 'gazetteer_place',
          attributes: {
            id: 1,
            wok_id: 1,
            parent_id: 0,
            name: 'Illinois',
            placetype: 'region',
            country: 'United States',
            repo: 'whosonfirst-data-admin-us',
            latitude: 40,
            longitude: -89,
            min_latitude: 37,
            min_longitude: -91.5,
            max_latitude: 42.5,
            max_longitude: -87,
            is_current: 1,
            is_deprecated: 0,
            is_ceased: 0,
            is_superseded: 0,
            is_superseding: 0,
            superseded_by: null,
            supersedes: null,
            lastmodified: 0,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            display_name: 'Illinois, United States',
          },
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="*"
            element={
              <>
                <SearchField />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: /Place \(location filter\): Add a place/i,
      })
    );

    fireEvent.change(
      screen.getByRole('textbox', {
        name: 'Location: search for a place to limit your search',
      }),
      {
        target: { value: 'Illinois' },
      }
    );

    await waitFor(
      () => {
        expect(fetchNominatimSearchMock).toHaveBeenCalledWith('Illinois', 10);
      },
      { timeout: 1200 }
    );

    fireEvent.click(await screen.findByRole('button', { name: /Illinois/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Submit search' }));

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe).toHaveAttribute('data-pathname', '/search');

      const params = new URLSearchParams(
        probe.getAttribute('data-search') ?? ''
      );
      expect(params.get('include_filters[geo][type]')).toBe('bbox');
      expect(params.get('include_filters[geo][field]')).toBe('dcat_bbox');
      expect(params.get('include_filters[geo][relation]')).toBe('intersects');
    });
  });

  it('shows grouped autosuggest actions and supports scoped title search', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: async () => ({
        data: [
          {
            id: 'suggestion-1',
            type: 'suggestion',
            attributes: { text: 'chicago manual of style', score: 6 },
          },
        ],
      }),
    }) as unknown as typeof fetch;

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="*"
            element={
              <>
                <SearchField />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    const searchInput = screen.getByRole('searchbox', { name: 'Search input' });
    fireEvent.focus(searchInput);
    fireEvent.change(searchInput, {
      target: { value: 'chicago' },
    });

    await waitFor(
      () => {
        expect(
          screen.getByRole('button', { name: /chicago in title/i })
        ).toBeInTheDocument();
        expect(
          screen.getByRole('button', {
            name: /see all results for chicago/i,
          })
        ).toBeInTheDocument();
      },
      { timeout: 1500 }
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/suggest?q=chicago', {
        headers: { Accept: 'application/json' },
      });
    });

    fireEvent.click(screen.getByRole('button', { name: /chicago in title/i }));

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe).toHaveAttribute('data-pathname', '/search');

      const params = new URLSearchParams(
        probe.getAttribute('data-search') ?? ''
      );
      expect(params.get('q')).toBe('chicago');
      expect(params.get('search_field')).toBe('dct_title_s');
    });
  });

  it('does not fetch keyword suggestions on initial mount from URL state alone', async () => {
    render(
      <MemoryRouter initialEntries={['/search?q=chicago']}>
        <Routes>
          <Route path="*" element={<SearchField initialQuery="chicago" />} />
        </Routes>
      </MemoryRouter>
    );

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('renders an explicit advanced search button label', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="*" element={<SearchField showAdvancedButton />} />
        </Routes>
      </MemoryRouter>
    );

    expect(
      screen.getByRole('button', { name: /advanced search/i })
    ).toBeInTheDocument();
  });
});
