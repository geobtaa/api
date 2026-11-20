import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { request } from '../sets/api';
import { ResourceRelationships } from './ResourceRelationships';
vi.mock('../sets/api', () => ({ request: vi.fn() }));
it('links accessible records, retains unresolved IDs and paginates', async () => {
  const first = {
    items: [
      {
        relationship: 'Is part of',
        id: 'parent/a:b',
        title: 'Parent map',
        set_id: 'parent-managingSet',
      },
      {
        relationship: 'Related to',
        id: 'external-id',
        title: null,
        set_id: null,
      },
    ],
    total: 3,
    offset: 0,
    limit: 2,
  };
  vi.mocked(request)
    .mockResolvedValueOnce(first)
    .mockResolvedValueOnce({
      items: [
        {
          relationship: 'Has part',
          id: 'child',
          title: null,
          set_id: 'child-managingSet',
        },
      ],
      total: 3,
      offset: 2,
      limit: 2,
    })
    .mockResolvedValueOnce(first);
  render(
    <MemoryRouter>
      <ResourceRelationships id="map" />
    </MemoryRouter>
  );
  expect(
    await screen.findByRole('link', { name: 'Parent map' })
  ).toHaveAttribute(
    'href',
    '/resources/~cGFyZW50L2E6Yg?set_id=parent-managingSet'
  );
  expect(screen.getByText('external-id')).toBeVisible();
  expect(screen.getByText('Not available here')).toBeVisible();
  expect(
    screen.getByRole('button', { name: 'Previous relationships' })
  ).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Next relationships' }));
  expect(await screen.findByRole('link', { name: 'child' })).toBeVisible();
  expect(
    screen.getByRole('button', { name: 'Next relationships' })
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Previous relationships' })
  );
  expect(await screen.findByRole('link', { name: 'Parent map' })).toBeVisible();
});
it('allows retry and shows the empty state', async () => {
  vi.mocked(request)
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce({ items: [], total: 0, offset: 0, limit: 25 });
  render(
    <MemoryRouter>
      <ResourceRelationships id="map" />
    </MemoryRouter>
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Relationships could not load'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  await waitFor(() =>
    expect(screen.getByText('No saved relationships.')).toBeVisible()
  );
});
