import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { ResourceClassFilterTabs } from '../../../components/search/ResourceClassFilterTabs';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import * as api from '../../../services/api';

vi.mock('../../../services/api', () => ({
  fetchSearchResults: vi.fn(),
}));

const mockFetchSearchResults = vi.mocked(api.fetchSearchResults);

function makeFacetItems(
  items: Array<[string, number] | { value: string; hits: number; label?: string }>
) {
  return items.map((item) =>
    Array.isArray(item)
      ? item
      : {
          attributes: {
            value: item.value,
            hits: item.hits,
            label: item.label ?? item.value,
          },
        }
  );
}

describe('ResourceClassFilterTabs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const renderWithRouter = (initialUrl = '/search') => {
    const routes = [
      {
        path: '/search',
        element: <ResourceClassFilterTabs variant="header" />,
      },
    ];
    const router = createMemoryRouter(routes, {
      initialEntries: [initialUrl],
    });
    return render(<RouterProvider router={router} />);
  };

  it('excludes Collections, Series, and Other from displayed tabs', async () => {
    mockFetchSearchResults.mockResolvedValue({
      data: [],
      meta: {},
      links: {},
      included: [
        {
          type: 'facet',
          id: 'resource_class_agg',
          attributes: {
            items: makeFacetItems([
              ['Maps', 500],
              ['Datasets', 300],
              ['Web services', 150],
              ['Imagery', 100],
              ['Websites', 80],
              ['Collections', 50],
              ['Series', 30],
              ['Other', 20],
            ]),
          },
        },
      ],
    } as unknown as Awaited<ReturnType<typeof api.fetchSearchResults>>);

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /show all resources/i })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /filter by maps/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /filter by datasets/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /filter by web services/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /filter by imagery/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /filter by websites/i })).toBeInTheDocument();

    expect(screen.queryByRole('button', { name: /filter by collections/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /filter by series/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /filter by other/i })).not.toBeInTheDocument();
  });

  it('navigates to search with filter when a tab is clicked', async () => {
    mockFetchSearchResults.mockResolvedValue({
      data: [],
      meta: {},
      links: {},
      included: [
        {
          type: 'facet',
          id: 'resource_class_agg',
          attributes: {
            items: makeFacetItems([['Maps', 500]]),
          },
        },
      ],
    } as unknown as Awaited<ReturnType<typeof api.fetchSearchResults>>);

    const routes = [
      {
        path: '/search',
        element: <ResourceClassFilterTabs variant="header" />,
      },
    ];
    const router = createMemoryRouter(routes, {
      initialEntries: ['/search?q='],
    });
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /filter by maps/i })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole('button', { name: /filter by maps/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/search');
      expect(router.state.location.search).toContain('gbl_resourceClass_sm');
      expect(router.state.location.search).toContain('Maps');
    });
  });
});
