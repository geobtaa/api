import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { HomePage } from './HomePage';

// Retain dashboard coverage for when staff work management is enabled again.
vi.mock('../config/features', () => ({ showWorkManagement: true }));

const reviewUrl = `/api/v1/admin/tasks?work_type=review&due_to=${new Date().toISOString().slice(0, 10)}&offset=0&limit=5`;
const harvestUrl = `/api/v1/admin/tasks?work_type=ingest&due_to=${new Date().toISOString().slice(0, 10)}&offset=0&limit=5`;
const jobsUrl = '/api/v1/admin/jobs?offset=0&limit=5';
const response = (items: unknown[] = [], total = items.length) => ({
  ok: true,
  json: async () => ({ items, total, offset: 0, limit: 5 }),
});
const managingSet = {
  task_id: 'task-1',
  set_id: 'set-1',
  set_title: 'Wisconsin',
  due_on: '2026-09-23',
  title: 'Wisconsin maps',
  code: 'WI',
};
const job = {
  job_id: 'job-1',
  state: 'partially_succeeded',
  created_at: '2026-09-21T12:00:00Z',
};

function Destination() {
  const location = useLocation();
  return (
    <p>
      Destination: {location.pathname}
      {location.search}
    </p>
  );
}

function setup(fetch = vi.fn().mockResolvedValue(response())) {
  vi.stubGlobal('fetch', fetch);
  const view = render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="*" element={<Destination />} />
      </Routes>
    </MemoryRouter>
  );
  return { fetch, ...view };
}

afterEach(() => vi.unstubAllGlobals());

it.each([
  ['resources', 'Title or ID'],
  ['sources', 'Title or ID'],
  ['sets', 'Title, ID, or legacy code'],
  ['work', 'Title or ID'],
])('searches %s with a trimmed, encoded query', async (area, label) => {
  setup();
  fireEvent.change(screen.getByLabelText('Search in'), {
    target: { value: `/${area}` },
  });
  fireEvent.change(screen.getByLabelText(label), {
    target: { value: '  lakes & rivers  ' },
  });
  fireEvent.submit(screen.getByRole('search'));
  expect(
    await screen.findByText(`Destination: /${area}?q=lakes+%26+rivers`)
  ).toBeInTheDocument();
});

it('opens all Resources for an empty search and links to existing work areas', async () => {
  setup();
  expect(screen.getByRole('link', { name: 'Resources' })).toHaveAttribute(
    'href',
    '/resources'
  );
  expect(screen.getByRole('link', { name: 'Browse Sources' })).toHaveAttribute(
    'href',
    '/sources'
  );
  expect(screen.getByRole('link', { name: 'Browse Sets' })).toHaveAttribute(
    'href',
    '/sets'
  );
  expect(screen.getByRole('link', { name: 'Create Set' })).toHaveAttribute(
    'href',
    '/sets/new'
  );
  expect(screen.getByRole('link', { name: 'Browse Sets' })).toHaveAttribute(
    'href',
    '/sets'
  );
  expect(screen.getByRole('link', { name: 'Import CSV' })).toHaveAttribute(
    'href',
    '/resources/csv'
  );
  fireEvent.submit(screen.getByRole('search'));
  expect(
    await screen.findByText('Destination: /resources?q=')
  ).toBeInTheDocument();
});

it('shows scoped, bounded due work and recent jobs with links to the full lists', async () => {
  const { fetch } = setup(
    vi.fn(async (url: string) =>
      url === jobsUrl ? response([job], 12) : response([managingSet], 1234)
    )
  );
  const reviews = within(screen.getByRole('region', { name: 'Reviews due' }));
  expect(await reviews.findByText('1,234')).toBeInTheDocument();
  expect(
    reviews.getByText('Showing 1 of 1,234 · ordered by due date')
  ).toBeInTheDocument();
  expect(
    reviews.getByRole('link', { name: managingSet.title })
  ).toHaveAttribute('href', '/tasks/task-1');
  expect(
    reviews.getByRole('link', { name: 'View all reviews due' })
  ).toHaveAttribute(
    'href',
    `/work?work_type=review&due_to=${new Date().toISOString().slice(0, 10)}`
  );
  const harvests = within(screen.getByRole('region', { name: 'Ingests due' }));
  expect(
    harvests.getByRole('link', { name: managingSet.title })
  ).toHaveAttribute('href', '/tasks/task-1');
  expect(
    harvests.getByRole('link', { name: 'View all ingests due' })
  ).toHaveAttribute(
    'href',
    `/work?work_type=ingest&due_to=${new Date().toISOString().slice(0, 10)}`
  );
  const jobs = within(
    screen.getByRole('region', { name: 'Recent validation jobs' })
  );
  expect(jobs.getByText('partially succeeded')).toBeInTheDocument();
  expect(
    jobs.getByText('Latest 1 of 12 jobs · newest first')
  ).toBeInTheDocument();
  expect(
    jobs.getByRole('link', { name: 'Validation results for job-1' })
  ).toHaveAttribute('href', '/jobs/job-1');
  expect(jobs.getByRole('link', { name: 'View all jobs' })).toHaveAttribute(
    'href',
    '/jobs'
  );
  expect(fetch).toHaveBeenCalledTimes(3);
  for (const url of [reviewUrl, harvestUrl, jobsUrl]) {
    expect(fetch).toHaveBeenCalledWith(
      url,
      expect.objectContaining({
        credentials: 'same-origin',
        signal: expect.any(AbortSignal),
      })
    );
  }
});

it('distinguishes loading and genuine empty results', async () => {
  let resolve!: (value: ReturnType<typeof response>) => void;
  const pending = new Promise<ReturnType<typeof response>>((done) => {
    resolve = done;
  });
  setup(vi.fn().mockReturnValue(pending));
  expect(screen.getAllByRole('status')).toHaveLength(3);
  expect(
    screen.getByRole('button', { name: 'Refresh reviews due' })
  ).toBeDisabled();
  expect(
    screen.queryByText('No pending review Tasks are due.')
  ).not.toBeInTheDocument();
  resolve(response());
  expect(
    await screen.findByText('No pending review Tasks are due.')
  ).toBeInTheDocument();
  expect(
    screen.getByText('No pending ingest Tasks are due.')
  ).toBeInTheDocument();
  expect(screen.getByText(/No validation jobs yet/)).toBeInTheDocument();
});

it.each([401, 403])(
  'keeps other work usable when a panel returns %s',
  async (status) => {
    const { fetch } = setup(
      vi.fn(async (url: string) =>
        url === reviewUrl ? { ok: false, status } : response()
      )
    );
    const reviews = within(screen.getByRole('region', { name: 'Reviews due' }));
    expect(
      await reviews.findByText(
        'Sign-in or additional access is needed to view this work.'
      )
    ).toBeInTheDocument();
    expect(reviews.getByRole('link', { name: 'Check access' })).toHaveAttribute(
      'href',
      '/access'
    );
    expect(
      screen.getByText('No pending ingest Tasks are due.')
    ).toBeInTheDocument();
    expect(screen.getByRole('search')).toBeInTheDocument();
    expect(reviews.queryByText(/No active Sets/)).not.toBeInTheDocument();
    fetch.mockResolvedValue(response([managingSet]));
    fireEvent.click(
      reviews.getByRole('button', { name: 'Refresh reviews due' })
    );
    expect(
      await reviews.findByRole('link', { name: managingSet.title })
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(4);
  }
);

it.each(['network', 'server'])(
  'recovers from a %s failure without discarding a search',
  async (failure) => {
    const fetch = vi.fn(async (url: string) => {
      if (url !== jobsUrl) return response();
      if (failure === 'network') throw new Error('offline');
      return { ok: false, status: 503, json: async () => ({}) };
    });
    setup(fetch);
    fireEvent.change(screen.getByLabelText('Title or ID'), {
      target: { value: 'Wisconsin' },
    });
    expect(
      await screen.findByText(
        'Recent validation jobs could not be loaded. Refresh to try again.'
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/No validation jobs yet/)
    ).not.toBeInTheDocument();
    fetch.mockResolvedValue(response([job]));
    fireEvent.click(
      screen.getByRole('button', { name: 'Refresh recent validation jobs' })
    );
    expect(await screen.findByText('partially succeeded')).toBeInTheDocument();
    expect(screen.getByLabelText('Title or ID')).toHaveValue('Wisconsin');
  }
);

it('removes previously visible work when refreshed access is denied', async () => {
  const { fetch } = setup(
    vi
      .fn()
      .mockImplementation(async (url: string) =>
        url === jobsUrl ? response() : response([managingSet])
      )
  );
  const reviews = within(screen.getByRole('region', { name: 'Reviews due' }));
  await reviews.findByText(managingSet.title);
  fetch.mockResolvedValue({ ok: false, status: 403 });
  fireEvent.click(reviews.getByRole('button', { name: 'Refresh reviews due' }));
  await reviews.findByRole('link', { name: 'Check access' });
  expect(reviews.queryByText(managingSet.title)).not.toBeInTheDocument();
});

it('cancels outstanding reads when leaving the homepage', async () => {
  const { fetch, unmount } = setup(
    vi.fn(
      (_url: string, options: RequestInit) =>
        new Promise((_resolve, reject) => {
          options.signal?.addEventListener('abort', () =>
            reject(new Error('aborted'))
          );
        })
    )
  );
  unmount();
  await waitFor(() => {
    for (const [, options] of fetch.mock.calls)
      expect(options.signal?.aborted).toBe(true);
  });
});
