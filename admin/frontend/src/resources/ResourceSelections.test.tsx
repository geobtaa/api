import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { ResourceSelectionPage, SaveSelection } from './ResourceSelections';

import * as features from '../config/features';

const json = (value: unknown) => new Response(JSON.stringify(value));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it('saves all matching predicates with an idempotent retry', async () => {
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce(json({ selection_id: 'saved', total: 1005 }));
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <SaveSelection
        q="County"
        setId="scope"
        filters='{"provider":["University"]}'
        total={1005}
      />
    </MemoryRouter>
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Select all 1005 matching Resources' })
  );
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button'));
  expect(
    await screen.findByRole('link', { name: 'Review saved selection' })
  ).toHaveAttribute('href', '/resources/selections/saved');
  expect(fetch.mock.calls[0][1].headers['Idempotency-Key']).toBe(
    fetch.mock.calls[1][1].headers['Idempotency-Key']
  );
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    q: 'County',
    set_id: 'scope',
    filters: { provider: ['University'] },
  });
});
it('shows saved/current versions, paginates and hides results after revocation', async () => {
  const fetch = vi.fn(async () =>
    json({
      total: 101,
      validation_set_id: 'scope',
      items: [
        {
          resource_id: 'one',
          set_id: 'scope',
          resource_version: 1,
          current_version: 2,
        },
        {
          resource_id: 'two',
          set_id: 'scope',
          resource_version: 1,
          current_version: 1,
        },
      ],
    })
  );
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter initialEntries={['/resources/selections/saved']}>
      <Routes>
        <Route
          path="/resources/selections/:selectionId"
          element={<ResourceSelectionPage />}
        />
      </Routes>
    </MemoryRouter>
  );
  await screen.findByText('Changed since selection');
  expect(
    screen.queryByRole('button', { name: 'Validate saved selection' })
  ).not.toBeInTheDocument();
  expect(screen.getByText('Unchanged')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Next selection page' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('offset=100'),
      expect.anything()
    )
  );
  await screen.findByRole('table');
  fireEvent.click(
    screen.getByRole('button', { name: 'Previous selection page' })
  );
  await screen.findByRole('table');
  fetch.mockRejectedValue(new Error('revoked'));
  fireEvent.click(screen.getByRole('button', { name: 'Refresh selection' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

it('submits the saved selection with a stable key after a lost response', async () => {
  vi.spyOn(
    features as { showWorkManagement: boolean },
    'showWorkManagement',
    'get'
  ).mockReturnValue(true);
  let attempts = 0;
  const fetch = vi.fn(async (url: string) => {
    if (url === '/api/v1/admin/jobs') {
      attempts += 1;
      if (attempts === 1) throw new Error('offline');
      return json({ job_id: 'job-one' });
    }
    return json({ total: 1005, items: [], validation_set_id: 'scope' });
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter initialEntries={['/resources/selections/saved']}>
      <Routes>
        <Route
          path="/resources/selections/:selectionId"
          element={<ResourceSelectionPage />}
        />
        <Route path="/jobs/:jobId" element={<p>Durable job progress</p>} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Validate saved selection' })
  );
  await screen.findByRole('alert');
  fireEvent.click(
    screen.getByRole('button', { name: 'Validate saved selection' })
  );
  await screen.findByText('Durable job progress');
  const calls = vi
    .mocked(fetch)
    .mock.calls.filter(([url]) => url === '/api/v1/admin/jobs') as unknown as [
    string,
    RequestInit,
  ][];
  expect(calls[0][1].headers).toEqual(calls[1][1].headers);
  expect(JSON.parse(calls[0][1].body as string)).toEqual({
    set_id: 'scope',
    selection_id: 'saved',
  });
});
