import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { Header } from '../../../components/layout/Header';

vi.mock('../../../components/SearchField', () => ({
  SearchField: () => <input aria-label="Search" />,
}));

vi.mock('../../../components/search/ResourceClassFilterTabs', () => ({
  ResourceClassFilterTabs: ({ layout }: { layout?: string }) => (
    <div data-testid={`resource-class-filter-tabs-${layout ?? 'horizontal'}`}>
      Resource Class Tabs
    </div>
  ),
}));

function renderHeader(initialEntry: string) {
  const router = createMemoryRouter([{ path: '*', element: <Header /> }], {
    initialEntries: [initialEntry],
  });

  return render(<RouterProvider router={router} />);
}

describe('Header', () => {
  it('shows Resource Class tabs on the homepage', () => {
    renderHeader('/');

    expect(screen.getAllByTestId(/resource-class-filter-tabs/)).toHaveLength(2);
  });

  it('hides Resource Class tabs on the search results page', () => {
    renderHeader('/search?q=lakes');

    expect(
      screen.queryByTestId('resource-class-filter-tabs-horizontal')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('resource-class-filter-tabs-vertical')
    ).not.toBeInTheDocument();
  });
});
