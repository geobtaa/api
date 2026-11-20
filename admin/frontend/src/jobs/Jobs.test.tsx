import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { JobList, JobPage, ValidateSelection } from './Jobs';
import type { Resource } from '../resources/ResourcePages';

const resource: Resource = {
  id: 'one',
  source_id: 'parent',
  set_id: 'scope',
  set_title: 'County',
  lock_version: 2,
  publication_state: 'draft',
  metadata: {},
};
const job = {
  job_id: 'job-one',
  set_id: 'scope',
  state: 'running',
  attempt_number: 1,
  totals: { pending: 1 },
};
const page = {
  items: [
    {
      position: 1,
      resource_id: 'one',
      resource_version: 2,
      disposition: 'pending',
      details: {},
    },
  ],
  total: 101,
};
const json = (value: unknown) => new Response(JSON.stringify(value));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
function detail() {
  render(
    <MemoryRouter initialEntries={['/jobs/job-one']}>
      <Routes>
        <Route path="/jobs/:jobId" element={<JobPage />} />
      </Routes>
    </MemoryRouter>
  );
}

it('retains the submission key after an uncertain response and exposes durable navigation', async () => {
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce(json(job));
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <ValidateSelection selection={[resource]} />
    </MemoryRouter>
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Validate selected drafts' })
  );
  await screen.findByRole('alert');
  fireEvent.click(
    screen.getByRole('button', { name: 'Retry validation submission' })
  );
  expect(
    await screen.findByRole('link', { name: 'View validation job' })
  ).toHaveAttribute('href', '/jobs/job-one');
  expect(fetch.mock.calls[0][1].headers['Idempotency-Key']).toBe(
    fetch.mock.calls[1][1].headers['Idempotency-Key']
  );
  expect(JSON.parse(fetch.mock.calls[1][1].body).selection).toEqual([
    { resource_id: 'one', lock_version: 2 },
  ]);
});

it('requires one Set in the explicit selection', () => {
  render(
    <MemoryRouter>
      <ValidateSelection
        selection={[resource, { ...resource, id: 'two', set_id: 'other' }]}
      />
    </MemoryRouter>
  );
  expect(
    screen.getByRole('button', { name: 'Validate selected drafts' })
  ).toBeDisabled();
});

it('reads durable results, pages server-side, confirms cancellation and refreshes safely', async () => {
  let currentJob: Omit<typeof job, 'totals'> & {
    totals: Record<string, number>;
  } = job;
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'POST')
      return json(
        (currentJob = { ...job, state: 'cancelled', totals: { cancelled: 1 } })
      );
    if (url.includes('/admin/contracts/'))
      return json({ can_cancel: true, can_download: true });
    if (url.includes('/items')) return json(page);
    return json(currentJob);
  });
  vi.stubGlobal('fetch', fetch);
  detail();
  expect(await screen.findByText(/running · attempt 1/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Next results' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('offset=100'),
      expect.anything()
    )
  );
  await screen.findByRole('table');
  fireEvent.click(screen.getByRole('button', { name: 'Previous results' }));
  expect(
    screen.getByRole('button', { name: 'Cancel remaining work' })
  ).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(
    screen.getByRole('button', { name: 'Cancel remaining work' })
  );
  expect(
    await screen.findByRole('link', { name: 'Download validation report' })
  ).toHaveAttribute('href', '/api/v1/admin/jobs/job-one/report');
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
});

it('recovers denied reads and clears stale results on a failed refresh', async () => {
  const fetch = vi.fn().mockRejectedValue(new Error('offline'));
  vi.stubGlobal('fetch', fetch);
  detail();
  await waitFor(() => expect(screen.getByRole('alert')).toHaveFocus());
  fetch.mockImplementation(async (url: string) =>
    json(
      url.includes('/admin/contracts/')
        ? {}
        : url.includes('/items')
          ? {
              ...page,
              items: [
                {
                  ...page.items[0],
                  disposition: 'invalid',
                  details: {
                    errors: ['Missing title'],
                    warnings: ['Missing schema'],
                    code: 'invalid_record',
                  },
                },
              ],
            }
          : { ...job, state: 'failed' }
    )
  );
  fireEvent.click(screen.getByRole('button', { name: 'Refresh job' }));
  expect(
    await screen.findByText('Missing title; Missing schema; invalid record')
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'Download validation report' })
  ).not.toBeInTheDocument();
  fetch.mockRejectedValue(new Error('revoked'));
  fireEvent.click(screen.getByRole('button', { name: 'Refresh job' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

it('requires refresh after uncertain cancellation', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      if (options?.method === 'POST') throw new Error('offline');
      return json(
        url.includes('/admin/contracts/')
          ? { can_cancel: true }
          : url.includes('/items')
            ? page
            : job
      );
    })
  );
  detail();
  await screen.findByRole('checkbox');
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(
    screen.getByRole('button', { name: 'Cancel remaining work' })
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Cancellation could not be confirmed'
  );
});

it('discovers prior submissions with pagination and read recovery', async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async () => json({ items: [job], total: 101 }));
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <JobList />
    </MemoryRouter>
  );
  expect(
    await screen.findByRole('link', { name: /Resource validation · job-one/ })
  ).toHaveAttribute('href', '/jobs/job-one');
  fireEvent.click(screen.getByRole('button', { name: 'Next jobs' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('offset=100'),
      expect.anything()
    )
  );
  await screen.findByRole('link');
  fireEvent.click(screen.getByRole('button', { name: 'Previous jobs' }));
  await screen.findByRole('link');
  fetch.mockRejectedValue(new Error('denied'));
  fireEvent.click(screen.getByRole('button', { name: 'Refresh jobs' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});
