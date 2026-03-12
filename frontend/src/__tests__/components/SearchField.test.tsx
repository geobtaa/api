import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { SearchField } from '../../components/SearchField';

const fetchNominatimSearchMock = vi.fn();

vi.mock('../../services/api', () => ({
  fetchNominatimSearch: (...args: unknown[]) => fetchNominatimSearchMock(...args),
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

  it('defaults header place bbox searches to within', async () => {
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
        name: /Place \(location filter\): Everywhere/i,
      })
    );

    fireEvent.change(
      screen.getByRole('textbox', {
        name: 'Place: search for a location to limit your search',
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

      const params = new URLSearchParams(probe.getAttribute('data-search') ?? '');
      expect(params.get('include_filters[geo][type]')).toBe('bbox');
      expect(params.get('include_filters[geo][field]')).toBe('dcat_bbox');
      expect(params.get('include_filters[geo][relation]')).toBe('within');
    });
  });
});
