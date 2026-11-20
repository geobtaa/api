import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkPage } from './Work';
import { MaintenancePage } from './Maintenance';
import { NewPeriodPage, NewTaskPage, TaskPage } from './TaskEditor';
import type { Task } from './api';

const rights = {
  create: true,
  update: true,
  complete: true,
  configure: true,
  report: true,
  work_types: ['review', 'ingest', 'other'],
  statuses: ['open', 'in_progress', 'blocked', 'completed', 'cancelled'],
};
const item: Task = {
  task_id: 'task-1',
  set_id: 'set-1',
  set_title: 'Aerial imagery',
  source_id: 'source-1',
  source_title: 'State library',
  title: 'Review imagery',
  description: 'Check the catalog',
  work_type: 'review',
  status: 'open',
  due_on: '2026-08-31',
  planned_on: '2026-09-02',
  assignee_id: null,
  assignee_name: null,
  recurring: true,
  predecessor_id: null,
  lock_version: 1,
  created_at: '2026-08-01T00:00:00Z',
  completed_at: null,
  completion_recorded_at: null,
  completed_by_name: null,
  completion_summary: null,
  evidence: [],
  processed_count: 0,
  changed_count: 0,
};
const period = {
  period_id: 'fall',
  name: 'Fall Semester 2026',
  starts_on: '2026-08-24',
  ends_on: '2026-12-18',
};
function ok(data: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}
function mock(items = [item]) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method && init.method !== 'GET')
      return ok({ ...item, ...JSON.parse(String(init.body)) });
    if (url.includes('/contracts/tasks')) return ok(rights);
    if (url.includes('/assignees'))
      return ok([{ actor_id: 'staff-1', display_name: 'Karen' }]);
    if (url.includes('/activity'))
      return ok({ items: [], total: 0, offset: 0, limit: 20 });
    if (url.includes('/maintenance')) return ok([]);
    if (url.includes('/work-periods')) return ok([period]);
    if (url.includes('/tasks/report'))
      return ok({
        completed: 1,
        processed: 200,
        changed: 12,
        late: 1,
        total_groups: 1,
        offset: 0,
        limit: 100,
        groups: [
          {
            key: 'set-1',
            label: 'Aerial imagery',
            completed: 1,
            processed: 200,
            changed: 12,
            late: 1,
          },
        ],
      });
    if (url.includes('/sets?'))
      return ok({
        items: [{ set_id: 'set-1', title: 'Aerial imagery' }],
        total: 1,
      });
    if (url.includes('/sets/set-1'))
      return ok({ title: 'Aerial imagery', status: 'active' });
    if (url.includes('/tasks/task-1')) return ok(items[0]);
    return ok({ items, total: items.length, offset: 0, limit: 100 });
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
function show(url = '/work') {
  const router = createMemoryRouter(
    [
      { path: '/work', element: <WorkPage /> },
      { path: '/tasks/new', element: <NewTaskPage /> },
      { path: '/tasks/:taskId', element: <TaskPage /> },
      { path: '/work/periods/new', element: <NewPeriodPage /> },
      { path: '/sets/:setId/maintenance', element: <MaintenancePage /> },
    ],
    { initialEntries: [url] }
  );
  render(<RouterProvider router={router} />);
  return router;
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('shows overdue work, server-owned types, and recoverable queue filters', async () => {
  const fetch = mock();
  show();
  expect(
    await screen.findByRole('link', { name: 'Review imagery' })
  ).toHaveAttribute('href', '/tasks/task-1');
  expect(screen.getByText('Overdue')).toBeVisible();
  expect(screen.getByText('Unassigned')).toBeVisible();
  fireEvent.click(screen.getByLabelText('Unassigned only'));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([url]) => url.includes('unassigned=true'))
    ).toBe(true)
  );
  fireEvent.click(screen.getByLabelText('Overdue only'));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => url.includes('due_to='))).toBe(true)
  );
  fireEvent.change(screen.getByLabelText('Work type'), {
    target: { value: 'ingest' },
  });
  fireEvent.change(screen.getByLabelText('Find work'), {
    target: { value: 'maps' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url]) => url.includes('q=maps') && url.includes('work_type=ingest')
      )
    ).toBe(true)
  );
});
it('uses planned date for the Calendar while retaining the original due date', async () => {
  const fetch = mock();
  show('/work?view=calendar&month=2026-09');
  const day = await screen.findByRole('region', { name: '2026-09-02' });
  expect(
    within(day).getByRole('link', { name: 'Review imagery' })
  ).toBeVisible();
  expect(
    fetch.mock.calls.some(
      ([url]) =>
        url.includes('calendar_from=2026-09-01') &&
        url.includes('calendar_to=2026-09-30')
    )
  ).toBe(true);
  fireEvent.change(screen.getByLabelText('Calendar month'), {
    target: { value: '2026-10' },
  });
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([url]) => url.includes('calendar_to=2026-10-31'))
    ).toBe(true)
  );
});
it('reports actual completions and uses a named semester range', async () => {
  const completed = {
    ...item,
    status: 'completed',
    completed_at: '2026-09-02T12:00:00Z',
    completion_recorded_at: '2026-10-01T12:00:00Z',
    completed_by_name: 'Karen',
  };
  const fetch = mock([completed]);
  show('/work?view=completed&starts_on=2026-09-01&ends_on=2026-09-30');
  expect(await screen.findByText(/200 Resources processed/)).toBeVisible();
  expect(await screen.findByText('Karen')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Reporting period'), {
    target: { value: 'fall' },
  });
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url]) =>
          url.includes('/report?') &&
          url.includes('starts_on=2026-08-24') &&
          url.includes('ends_on=2026-12-18')
      )
    ).toBe(true)
  );
  fireEvent.change(screen.getByLabelText('Group accomplishments by'), {
    target: { value: 'completed_by' },
  });
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([url]) => url.includes('group_by=completed_by'))
    ).toBe(true)
  );
});
it('shows an empty queue without fabricating scheduled work', async () => {
  mock([]);
  show();
  expect(
    await screen.findByText('No work matches these filters.')
  ).toBeVisible();
});
it('creates a Set Task and retains its idempotency key after an uncertain response', async () => {
  const fetch = mock();
  show('/tasks/new');
  fireEvent.click(await screen.findByRole('radio'));
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'Review imagery' },
  });
  await screen.findByLabelText('Assignee');
  fetch.mockRejectedValueOnce(new Error('offline'));
  fireEvent.click(screen.getByRole('button', { name: 'Create Task' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'API could not be reached'
  );
  expect(screen.getByLabelText('Title (required)')).toHaveValue(
    'Review imagery'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Create Task' }));
  await screen.findByRole('heading', { name: 'Review imagery' });
  const calls = fetch.mock.calls.filter(([, init]) => init?.method === 'POST');
  expect(calls).toHaveLength(2);
  expect(calls[0][1]?.headers).toEqual(calls[1][1]?.headers);
  expect(JSON.parse(String(calls[1][1]?.body))).toMatchObject({
    set_id: 'set-1',
    title: 'Review imagery',
    assignee_id: null,
  });
});
it('records actual completion, counts and evidence while retaining the occurrence', async () => {
  const fetch = mock();
  show('/tasks/task-1');
  fireEvent.click(await screen.findByText('Complete this occurrence'));
  fireEvent.change(screen.getByLabelText('Completed at (UTC)'), {
    target: { value: '2026-09-02T12:00' },
  });
  fireEvent.change(screen.getByLabelText('What was completed? (required)'), {
    target: { value: 'Reviewed the catalog' },
  });
  fireEvent.change(screen.getByLabelText('Resources processed'), {
    target: { value: '200' },
  });
  fireEvent.change(screen.getByLabelText('Resources changed'), {
    target: { value: '12' },
  });
  fireEvent.change(screen.getByLabelText('Evidence URL'), {
    target: { value: 'https://example.org/report' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Complete Task' }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url, init]) => url.endsWith('/completion') && init?.method === 'POST'
      )
    ).toBe(true)
  );
  const call = fetch.mock.calls.find(
    ([url, init]) => url.endsWith('/completion') && init?.method === 'POST'
  )!;
  expect(JSON.parse(String(call[1]?.body))).toMatchObject({
    completed_at: '2026-09-02T12:00:00Z',
    processed_count: 200,
    changed_count: 12,
    summary: 'Reviewed the catalog',
    evidence: [
      { label: 'Completion evidence', url: 'https://example.org/report' },
    ],
  });
});
it('keeps an edit draft during optimistic conflict recovery', async () => {
  const fetch = mock();
  show('/tasks/task-1');
  fireEvent.click(await screen.findByText('Edit Task'));
  await screen.findByLabelText('Assignee');
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'My edited title' },
  });
  fireEvent.change(screen.getByLabelText('Reason for change (required)'), {
    target: { value: 'Assign review' },
  });
  fetch.mockResolvedValueOnce(
    ok(
      {
        detail: {
          code: 'stale_version',
          message: 'Reload current Task',
          errors: [],
        },
      },
      409
    )
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save Task' }));
  const reload = await screen.findByRole('button', {
    name: 'Load current version; keep my draft',
  });
  fetch.mockResolvedValueOnce(
    ok({ ...item, lock_version: 2, title: 'Another editor’s title' })
  );
  fireEvent.click(reload);
  await screen.findByText(/Current saved version 2/);
  expect(screen.getByLabelText('Title')).toHaveValue('My edited title');
  fireEvent.click(screen.getByRole('button', { name: 'Save Task' }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.filter(([, init]) => init?.method === 'PATCH')
    ).toHaveLength(2)
  );
  const last = fetch.mock.calls.filter(
    ([, init]) => init?.method === 'PATCH'
  )[1];
  expect(JSON.parse(String(last[1]?.body))).toMatchObject({
    lock_version: 2,
    title: 'My edited title',
  });
});
it('shows immutable completion evidence and both completion and recording dates', async () => {
  mock([
    {
      ...item,
      status: 'completed',
      completed_at: '2026-09-02T12:00:00Z',
      completion_recorded_at: '2026-10-01T12:00:00Z',
      completed_by_name: 'Karen',
      completion_summary: 'Reviewed catalog',
      evidence: [{ label: 'Report', url: 'https://example.org/report' }],
      processed_count: 200,
      changed_count: 12,
    },
  ]);
  show('/tasks/task-1');
  expect(
    await screen.findByRole('region', { name: 'Completion evidence' })
  ).toHaveTextContent('Reviewed catalog');
  expect(screen.getByText('2026-10-01T12:00:00Z')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Report' })).toHaveAttribute(
    'href',
    'https://example.org/report'
  );
  expect(
    screen.queryByText('Complete this occurrence')
  ).not.toBeInTheDocument();
});
it('saves an explicit semester range and opens its accomplishments view', async () => {
  const fetch = mock();
  const router = show('/work/periods/new');
  fireEvent.change(screen.getByLabelText('Name'), {
    target: { value: 'Fall Semester 2026' },
  });
  fireEvent.change(screen.getByLabelText('Starts on'), {
    target: { value: '2026-08-24' },
  });
  fireEvent.change(screen.getByLabelText('Ends on'), {
    target: { value: '2026-12-18' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save period' }));
  await waitFor(() =>
    expect(router.state.location.search).toContain('starts_on=2026-08-24')
  );
  expect(
    fetch.mock.calls.some(
      ([url, init]) =>
        url === '/api/v1/admin/work-periods' && init?.method === 'POST'
    )
  ).toBe(true);
});
it('configures Set review recurrence with a first due date', async () => {
  const fetch = mock();
  show('/sets/set-1/maintenance');
  const form = await screen.findByRole('form', { name: 'review maintenance' });
  fireEvent.change(within(form).getByLabelText('First Task due date'), {
    target: { value: '2026-10-15' },
  });
  fireEvent.click(
    within(form).getByRole('button', { name: 'Save maintenance' })
  );
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url, init]) =>
          url.endsWith('/maintenance/review') && init?.method === 'PUT'
      )
    ).toBe(true)
  );
  const call = fetch.mock.calls.find(
    ([url, init]) =>
      url.endsWith('/maintenance/review') && init?.method === 'PUT'
  )!;
  expect(JSON.parse(String(call[1]?.body))).toMatchObject({
    lock_version: 0,
    interval: 'P6M',
    next_due_on: '2026-10-15',
    enabled: true,
  });
});

it('protects unsaved Task drafts during navigation and supports explicit discard', async () => {
  mock();
  show('/tasks/new');
  fireEvent.change(await screen.findByLabelText('Title (required)'), {
    target: { value: 'My draft' },
  });
  fireEvent.click(screen.getByRole('link', { name: '← Work' }));
  const dialog = await screen.findByRole('dialog');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByLabelText('Title (required)')).toHaveValue('My draft');
  fireEvent.click(screen.getByRole('link', { name: '← Work' }));
  fireEvent.click(
    within(await screen.findByRole('dialog')).getByRole('button', {
      name: 'Discard changes',
    })
  );
  expect(await screen.findByRole('heading', { name: 'Work' })).toBeVisible();
});

it('does not discard a second form draft when completing work', async () => {
  const fetch = mock();
  show('/tasks/task-1');
  fireEvent.change(await screen.findByLabelText('Title'), {
    target: { value: 'Revised instructions' },
  });
  fireEvent.change(screen.getByLabelText('What was completed? (required)'), {
    target: { value: 'Reviewed' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Complete Task' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('other form');
  expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
    false
  );
  expect(screen.getByLabelText('Title')).toHaveValue('Revised instructions');
});

it('preserves an assignment while choices load and prevents editing during a save', async () => {
  const fetch = mock([
    { ...item, assignee_id: 'staff-1', assignee_name: 'Karen' },
  ]);
  const original = fetch.getMockImplementation()!;
  let finish: (value: ReturnType<typeof ok>) => void = () => {};
  fetch.mockImplementation((url, init) => {
    if (url.includes('/assignees')) return new Promise(() => {});
    if (init?.method === 'PATCH')
      return new Promise((resolve) => {
        finish = resolve;
      });
    return original(url, init);
  });
  show('/tasks/task-1');
  const title = await screen.findByLabelText('Title');
  fireEvent.change(title, { target: { value: 'Revised review' } });
  fireEvent.change(screen.getByLabelText('Reason for change (required)'), {
    target: { value: 'Clarify instructions' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Task' }));
  await waitFor(() => expect(title).toBeDisabled());
  const patch = fetch.mock.calls.find(([, init]) => init?.method === 'PATCH')!;
  expect(JSON.parse(String(patch[1]?.body)).assignee_id).toBe('staff-1');
  finish(ok({ ...item, lock_version: 2 }));
  await waitFor(() =>
    expect(screen.getByLabelText('Title')).not.toBeDisabled()
  );
});
