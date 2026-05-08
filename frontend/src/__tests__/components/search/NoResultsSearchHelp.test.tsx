import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NoResultsSearchHelp } from '../../../components/search/NoResultsSearchHelp';
import { fetchNominatimSearch } from '../../../services/api';
import type { GazetteerPlace, GazetteerResponse } from '../../../types/api';

vi.mock('../../../services/api', () => ({
  fetchNominatimSearch: vi.fn(),
}));

const createPlace = (): GazetteerPlace => ({
  id: 'nominatim-123',
  type: 'gazetteer-place',
  attributes: {
    name: 'Madison',
    placetype: 'city',
    country: 'United States',
    repo: 'nominatim',
    latitude: 43.0748,
    longitude: -89.384,
    min_latitude: 42.99,
    min_longitude: -89.57,
    max_latitude: 43.18,
    max_longitude: -89.25,
    is_current: 1,
    is_deprecated: 0,
    is_ceased: 0,
    is_superseded: 0,
    is_superseding: 0,
    superseded_by: null,
    supersedes: null,
    lastmodified: 0,
    created_at: '',
    updated_at: '',
    display_name: 'Madison, Dane County, Wisconsin, United States',
  },
});

const createGazetteerResponse = (
  places: GazetteerPlace[]
): GazetteerResponse => ({
  jsonapi: { version: '1.1', profile: [] },
  links: { self: '' },
  meta: {
    totalCount: places.length,
    totalPages: 1,
    currentPage: 1,
    perPage: 5,
    query: 'grassland',
    offset: 0,
    gazetteer: 'nominatim',
  },
  data: places,
});

describe('NoResultsSearchHelp', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: [
          { attributes: { text: 'grassland maps' } },
          { attributes: { text: 'grassland data' } },
        ],
      }),
    }) as unknown as typeof fetch;
    vi.mocked(fetchNominatimSearch).mockResolvedValue(
      createGazetteerResponse([createPlace()])
    );
  });

  it('shows geographic, keyword, and advanced search suggestions for the failed query', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/search?q=grassland&view=gallery&per_page=20&search_field=dct_subject_sm,dcat_theme_sm',
        ]}
      >
        <NoResultsSearchHelp
          query="grassland"
          advancedSearchHref="/search?q=grassland&showAdvanced=true"
        />
      </MemoryRouter>
    );

    expect(screen.getByRole('status')).toHaveTextContent(
      'No search results found'
    );
    expect(await screen.findByText('grassland maps')).toBeInTheDocument();
    expect(screen.getByText('Geographic Areas')).toBeInTheDocument();
    expect(screen.getByText('Suggestions')).toBeInTheDocument();
    expect(screen.getByText('Via OpenStreetMap')).toBeInTheDocument();
    expect(screen.queryByText('Search Only In')).not.toBeInTheDocument();

    const geographicAreasHeading = screen.getByText('Geographic Areas');
    const suggestionsHeading = screen.getByText('Suggestions');
    expect(
      geographicAreasHeading.compareDocumentPosition(suggestionsHeading) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();

    const keywordLink = screen.getByRole('link', {
      name: /grassland maps/i,
    });
    expect(keywordLink).toHaveAttribute(
      'href',
      expect.stringContaining('q=grassland+maps')
    );
    expect(keywordLink).toHaveAttribute(
      'href',
      expect.stringContaining('view=gallery')
    );

    expect(
      screen.queryByRole('link', { name: /grassland in title/i })
    ).toBeNull();
    expect(
      screen.queryByRole('link', { name: /grassland in subject\/theme/i })
    ).toBeNull();

    const placeLink = await screen.findByRole('link', {
      name: /madison \(city\)/i,
    });
    expect(placeLink).toHaveAttribute(
      'href',
      expect.stringContaining('include_filters%5Bgeo%5D%5Btype%5D=bbox')
    );
    expect(placeLink).toHaveAttribute('href', expect.stringContaining('q='));
    expect(placeLink).toHaveAttribute(
      'href',
      expect.not.stringContaining('search_field')
    );
    expect(placeLink).toHaveAttribute(
      'href',
      expect.stringContaining(
        'include_filters%5Bgeo%5D%5Brelation%5D=intersects'
      )
    );
    expect(
      screen.getAllByRole('link', { name: /advanced search/i })[0]
    ).toHaveAttribute('href', '/search?q=grassland&showAdvanced=true');

    await waitFor(() => {
      expect(fetchNominatimSearch).toHaveBeenCalledWith('grassland', 5);
    });
  });
});
