import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useFacetModal } from '../../hooks/useFacetModal';
import type { FacetValuesResponse } from '../../types/api';

// Mock fetchFacetValues
vi.mock('../../services/api', () => ({
  fetchFacetValues: vi.fn(),
}));

import { fetchFacetValues } from '../../services/api';

describe('useFacetModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockFacetResponse: FacetValuesResponse = {
    data: [
      {
        type: 'facet_value',
        id: 'Minnesota',
        attributes: {
          value: 'Minnesota',
          label: 'Minnesota',
          hits: 100,
        },
      },
      {
        type: 'facet_value',
        id: 'Wisconsin',
        attributes: {
          value: 'Wisconsin',
          label: 'Wisconsin',
          hits: 50,
        },
      },
    ],
    meta: {
      totalCount: 2,
      totalPages: 1,
      currentPage: 1,
      perPage: 10,
      facetName: 'dct_spatial_sm',
      sort: 'count_desc',
    },
  };

  it('loads facet values when modal opens', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    expect(fetchFacetValues).toHaveBeenCalledWith({
      facetName: 'dct_spatial_sm',
      searchParams: expect.any(URLSearchParams),
      page: 1,
      perPage: 10,
      sort: 'count_desc',
      qFacet: undefined,
    });
    expect(result.current.items).toHaveLength(2);
    expect(result.current.meta).toEqual(mockFacetResponse.meta);
  });

  it('does not load when modal is closed', () => {
    renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: false,
        searchParams: new URLSearchParams(),
      })
    );

    expect(fetchFacetValues).not.toHaveBeenCalled();
  });

  it('resets state when modal closes', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result, rerender } = renderHook(
      ({ isOpen }) =>
        useFacetModal({
          facetId: 'dct_spatial_sm',
          isOpen,
          searchParams: new URLSearchParams(),
        }),
      {
        initialProps: { isOpen: true },
      }
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    // Close modal
    rerender({ isOpen: false });

    // Wait for the effect to run and reset state
    await waitFor(
      () => {
        expect(result.current.hasLoaded).toBe(false);
        expect(result.current.items).toHaveLength(0);
        expect(result.current.meta).toBeNull();
      },
      { timeout: 2000 }
    );
  });

  it('handles pagination', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    vi.mocked(fetchFacetValues).mockClear();

    result.current.setPage(2);

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 2,
        })
      );
    });
  });

  it('handles sort changes', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    vi.mocked(fetchFacetValues).mockClear();

    result.current.setSort('alpha_asc');

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          sort: 'alpha_asc',
          page: 1, // Should reset to page 1
        })
      );
    });
  });

  it('handles perPage changes', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    vi.mocked(fetchFacetValues).mockClear();

    result.current.setPerPage(20);

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          perPage: 20,
          page: 1, // Should reset to page 1
        })
      );
    });
  });

  it('handles facet query (qFacet)', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    vi.mocked(fetchFacetValues).mockClear();

    result.current.setFacetQuery('Minnesota');

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          qFacet: 'Minnesota',
          page: 1, // Should reset to page 1
        })
      );
    });
  });

  it('resets facet query', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    // Set query first
    result.current.setFacetQuery('Minnesota');
    await waitFor(() => {
      expect(result.current.qFacet).toBe('Minnesota');
    });

    vi.mocked(fetchFacetValues).mockClear();

    // Reset query
    result.current.resetFacetQuery();

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          qFacet: undefined, // Empty string becomes undefined in fetchFacetValues
          page: 1,
        })
      );
    });
  });

  it('handles errors', async () => {
    const error = new Error('Failed to fetch');
    vi.mocked(fetchFacetValues).mockRejectedValue(error);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.error).toBe('Failed to fetch');
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('forwards search params to API', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const searchParams = new URLSearchParams(
      'q=lakes&include_filters[dct_spatial_sm][]=Minnesota'
    );

    renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams,
      })
    );

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          searchParams: expect.any(URLSearchParams),
        })
      );
    });

    const callArgs = vi.mocked(fetchFacetValues).mock.calls[0][0];
    expect(callArgs.searchParams.get('q')).toBe('lakes');
  });

  it('reloads when search params change', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { rerender } = renderHook(
      ({ searchParams }) =>
        useFacetModal({
          facetId: 'dct_spatial_sm',
          isOpen: true,
          searchParams,
        }),
      {
        initialProps: { searchParams: new URLSearchParams('q=lakes') },
      }
    );

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalled();
    });

    vi.mocked(fetchFacetValues).mockClear();

    // Change search params
    rerender({ searchParams: new URLSearchParams('q=rivers') });

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalled();
    });
  });

  it('refetches data when refetch is called', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    vi.mocked(fetchFacetValues).mockClear();

    result.current.refetch();

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalled();
    });
  });

  it('normalizes page to minimum 1', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    // First, set page to 2 so we can test normalization from 0 to 1
    result.current.setPage(2);
    await waitFor(() => {
      expect(result.current.page).toBe(2);
    });

    vi.mocked(fetchFacetValues).mockClear();

    // Now test normalization from 0 to 1
    result.current.setPage(0);

    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1,
        })
      );
      expect(result.current.page).toBe(1);
    });
  });

  it('normalizes perPage to between 1 and 100', async () => {
    vi.mocked(fetchFacetValues).mockResolvedValue(mockFacetResponse);

    const { result } = renderHook(() =>
      useFacetModal({
        facetId: 'dct_spatial_sm',
        isOpen: true,
        searchParams: new URLSearchParams(),
      })
    );

    await waitFor(() => {
      expect(result.current.hasLoaded).toBe(true);
    });

    // Test minimum
    vi.mocked(fetchFacetValues).mockClear();
    result.current.setPerPage(0);
    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          perPage: 1,
        })
      );
    });

    // Test maximum
    vi.mocked(fetchFacetValues).mockClear();
    result.current.setPerPage(200);
    await waitFor(() => {
      expect(fetchFacetValues).toHaveBeenCalledWith(
        expect.objectContaining({
          perPage: 100,
        })
      );
    });
  });
});
