import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  act,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
    fetchNominatimSearchMock.mockResolvedValue({ data: [] });

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

  it('applies only a bbox filter when selecting a place suggestion', async () => {
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

    const searchInput = screen.getByRole('searchbox', { name: 'Search input' });
    fireEvent.focus(searchInput);
    fireEvent.change(searchInput, {
      target: { value: 'Illinois' },
    });

    await waitFor(
      () => {
        expect(fetchNominatimSearchMock).toHaveBeenCalledWith('Illinois', 5);
      },
      { timeout: 1200 }
    );

    fireEvent.click(
      await screen.findByRole('button', { name: /illinois \(region\)/i })
    );

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe).toHaveAttribute('data-pathname', '/search');

      const params = new URLSearchParams(
        probe.getAttribute('data-search') ?? ''
      );
      expect(params.get('include_filters[geo][type]')).toBe('bbox');
      expect(params.get('include_filters[geo][field]')).toBe('dcat_bbox');
      expect(params.get('include_filters[geo][relation]')).toBe('intersects');
      expect(params.get('q')).toBe('');
    });
  });

  it('clears keyword and fielded search when selecting a place suggestion from existing results', async () => {
    const user = userEvent.setup();
    fetchNominatimSearchMock.mockResolvedValue({
      data: [
        {
          id: 'milwaukee',
          type: 'gazetteer_place',
          attributes: {
            id: 1,
            wok_id: 1,
            parent_id: 0,
            name: 'Milwaukee',
            placetype: 'city',
            country: 'United States',
            repo: 'nominatim',
            latitude: 43.0389,
            longitude: -87.9065,
            min_latitude: 42.818,
            min_longitude: -88.0716,
            max_latitude: 43.1947,
            max_longitude: -87.8639,
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
            display_name:
              'Milwaukee, Milwaukee County, Wisconsin, United States',
          },
        },
      ],
    });

    const currentResultsUrl =
      '/search?q=New+york&view=gallery&per_page=20' +
      '&search_field=dct_subject_sm%2Cdcat_theme_sm' +
      '&include_filters%5Bgbl_resourceClass_sm%5D%5B%5D=Maps' +
      '&include_filters%5Bgeo%5D%5Btype%5D=bbox' +
      '&include_filters%5Bgeo%5D%5Bfield%5D=dcat_bbox' +
      '&include_filters%5Bgeo%5D%5Brelation%5D=intersects' +
      '&include_filters%5Bgeo%5D%5Btop_left%5D%5Blat%5D=45.0158611' +
      '&include_filters%5Bgeo%5D%5Btop_left%5D%5Blon%5D=-79.7619758' +
      '&include_filters%5Bgeo%5D%5Bbottom_right%5D%5Blat%5D=40.476578' +
      '&include_filters%5Bgeo%5D%5Bbottom_right%5D%5Blon%5D=-71.790972';

    render(
      <MemoryRouter initialEntries={[currentResultsUrl]}>
        <Routes>
          <Route
            path="*"
            element={
              <>
                <SearchField initialQuery="Madison" />
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
      target: { value: 'Milwaukee' },
    });

    await waitFor(
      () => {
        expect(fetchNominatimSearchMock).toHaveBeenCalledWith('Milwaukee', 5);
      },
      { timeout: 1200 }
    );

    await user.click(
      await screen.findByRole('button', { name: /milwaukee \(city\)/i })
    );

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe).toHaveAttribute('data-pathname', '/search');

      const params = new URLSearchParams(
        probe.getAttribute('data-search') ?? ''
      );
      expect(params.get('q')).toBe('');
      expect(params.get('search_field')).toBeNull();
      expect(params.get('page')).toBeNull();
      expect(params.get('view')).toBe('gallery');
      expect(params.get('per_page')).toBe('20');
      expect(params.getAll('include_filters[gbl_resourceClass_sm][]')).toEqual([
        'Maps',
      ]);
      expect(params.get('include_filters[geo][type]')).toBe('bbox');
      expect(params.get('include_filters[geo][relation]')).toBe('intersects');
      expect(params.get('include_filters[geo][top_left][lat]')).toBe('43.1947');
      expect(params.get('include_filters[geo][top_left][lon]')).toBe(
        '-88.0716'
      );
      expect(params.get('include_filters[geo][bottom_right][lat]')).toBe(
        '42.818'
      );
      expect(params.get('include_filters[geo][bottom_right][lon]')).toBe(
        '-87.8639'
      );
    });
  });

  it('shows geographic areas first and links to advanced search in autosuggest actions', async () => {
    fetchNominatimSearchMock.mockResolvedValue({
      data: [
        {
          id: 'chicago',
          type: 'gazetteer_place',
          attributes: {
            id: 1,
            wok_id: 1,
            parent_id: 0,
            name: 'Chicago',
            placetype: 'city',
            country: 'United States',
            repo: 'nominatim',
            latitude: 41.88,
            longitude: -87.63,
            min_latitude: 41.64,
            min_longitude: -87.94,
            max_latitude: 42.02,
            max_longitude: -87.52,
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
            display_name: 'Chicago, Cook County, Illinois, United States',
          },
        },
      ],
    });

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
          screen.queryByRole('button', { name: /chicago in title/i })
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole('button', { name: /chicago in subject\/theme/i })
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole('button', { name: /^chicago in subject$/i })
        ).not.toBeInTheDocument();
        expect(
          screen.getByRole('button', {
            name: /see all results for chicago/i,
          })
        ).toBeInTheDocument();
        expect(
          screen.getByRole('button', { name: /advanced search/i })
        ).toBeInTheDocument();
      },
      { timeout: 1500 }
    );

    await waitFor(
      () => {
        const geographicAreasHeading = screen.getByText('Geographic Areas');
        const suggestionsHeading = screen.getByText('Suggestions');

        expect(
          geographicAreasHeading.compareDocumentPosition(suggestionsHeading) &
            Node.DOCUMENT_POSITION_FOLLOWING
        ).toBeTruthy();
        expect(screen.getByText('Geographic Areas')).toBeInTheDocument();
        expect(screen.getByText('Via OpenStreetMap')).toBeInTheDocument();
        expect(
          screen.getByRole('button', { name: /chicago \(city\)/i })
        ).toBeInTheDocument();
        expect(screen.queryByText(/OpenStreetMap ·/i)).not.toBeInTheDocument();
      },
      { timeout: 1500 }
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/suggest?q=chicago', {
        headers: { Accept: 'application/json' },
      });
    });

    fireEvent.click(screen.getByRole('button', { name: /advanced search/i }));

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe).toHaveAttribute('data-pathname', '/search');

      const params = new URLSearchParams(
        probe.getAttribute('data-search') ?? ''
      );
      expect(params.get('q')).toBe('chicago');
      expect(params.get('showAdvanced')).toBe('true');
    });
  });

  it('clears the active fielded search from the search form chip', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/search?q=mineral&search_field=dct_subject_sm%2Cdcat_theme_sm&page=3&view=gallery',
        ]}
      >
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
        name: /clear fielded search: subject\/theme/i,
      })
    );

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      const params = new URLSearchParams(
        probe.getAttribute('data-search') ?? ''
      );

      expect(params.get('q')).toBe('mineral');
      expect(params.get('search_field')).toBeNull();
      expect(params.get('page')).toBeNull();
      expect(params.get('view')).toBe('gallery');
    });
  });

  it('distinguishes same-named geographic areas by place type', async () => {
    fetchNominatimSearchMock.mockResolvedValue({
      data: [
        {
          id: 'new-york-city',
          type: 'gazetteer_place',
          attributes: {
            id: 1,
            wok_id: 1,
            parent_id: 0,
            name: 'New York',
            placetype: 'city',
            country: 'United States',
            repo: 'nominatim',
            latitude: 40.7128,
            longitude: -74.006,
            min_latitude: 40.476578,
            min_longitude: -74.258843,
            max_latitude: 40.91763,
            max_longitude: -73.700233,
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
            display_name: 'New York, United States',
          },
        },
        {
          id: 'new-york-state',
          type: 'gazetteer_place',
          attributes: {
            id: 2,
            wok_id: 2,
            parent_id: 0,
            name: 'New York',
            placetype: 'state',
            country: 'United States',
            repo: 'nominatim',
            latitude: 43.1566,
            longitude: -75.8449,
            min_latitude: 40.476578,
            min_longitude: -79.7619758,
            max_latitude: 45.0158611,
            max_longitude: -71.790972,
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
            display_name: 'New York, United States',
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

    const searchInput = screen.getByRole('searchbox', { name: 'Search input' });
    fireEvent.focus(searchInput);
    fireEvent.change(searchInput, {
      target: { value: 'new york' },
    });

    await waitFor(
      () => {
        expect(
          screen.getByRole('button', { name: /new york \(city\)/i })
        ).toBeInTheDocument();
        expect(
          screen.getByRole('button', { name: /new york \(state\)/i })
        ).toBeInTheDocument();
      },
      { timeout: 1500 }
    );
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
