import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { SetList } from './SetBrowse';
import { SetPage } from './SetEditor';
import type { SetRecord } from './api';

const item: SetRecord = {
  set_id: 'State_Maps',
  source_id: 'parent',
  legacy_code: '05a-01',
  set_scope: 'All maps',
  status: 'active',
  endpoint_description: 'DCAT',
  workflow: 'py_umedia',
  review_interval: '3y',
  harvest_interval: 'Irregular',
  tags: 'ogm',
  title: 'State Maps',
  description: 'Maps and imagery',
  endpoint_url: 'https://example.org/maps',
  admin_notes: 'Staff context',
  lock_version: 1,
  updated_at: '2026-09-21T12:00:00Z',
};
const contract = {
  create: true,
  update: true,
  activity_read: true,
  fields: {
    status: { enum: ['active', 'inactive', 'retired'], default: 'active' },
    set_id: { maxLength: 128 },
    title: { maxLength: 250 },
    description: { maxLength: 5000 },
    endpoint_url: {},
    admin_notes: { maxLength: 10000 },
  },
};
const ok = (data: unknown) => ({ ok: true, json: async () => data });
const failed = (status: number, detail?: unknown) => ({
  ok: false,
  status,
  json: async () => ({ detail }),
});
const page = (
  items: unknown[],
  offset = 0,
  total = items.length,
  limit = 25
) => ({ items, total, offset, limit });
function setup(
  path: string,
  handler: (url: string, options?: RequestInit) => unknown = () => ok(item)
) {
  const fetch = vi.fn(async (url: string, options?: RequestInit) =>
    url.includes('/activity') &&
    (path.endsWith('/edit') || path.endsWith('/new'))
      ? ok(page([]))
      : url.endsWith('/workflow-catalog')
        ? ok([
            {
              workflow_id: 'py_ogm_aardvark',
              label: 'OpenGeoMetadata repository',
              description: 'OGM metadata',
              acquisition_mode: 'automated_retrieval',
            },
          ])
        : handler(url, options)
  );
  vi.stubGlobal('fetch', fetch);
  const router = createMemoryRouter(
    [
      { path: '/sets', element: <SetList /> },
      { path: '/sets/new', element: <SetPage mode="create" /> },
      {
        path: '/sets/:setId/edit',
        element: <SetPage mode="edit" />,
      },
      { path: '/sets/:setId', element: <SetPage /> },
    ],
    { initialEntries: [path] }
  );
  render(<RouterProvider router={router} />);
  return { fetch, router };
}
const input = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const click = (name: string) =>
  fireEvent.click(screen.getByRole('button', { name }));
afterEach(() => vi.unstubAllGlobals());

it('browses Sets with URL search, pagination, stable IDs and return context', async () => {
  const { router } = setup('/sets?q=Maps', (url) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (url.includes('?')) {
      const query = new URL(url, 'https://local').searchParams;
      return ok(
        page(
          query.get('q') === 'missing' ? [] : [item],
          Number(query.get('offset')),
          query.get('q') === 'missing' ? 0 : 30
        )
      );
    }
    return ok(item);
  });
  expect(screen.getByRole('status')).toHaveTextContent('Loading');
  expect(await screen.findByRole('link', { name: item.title })).toHaveAttribute(
    'href',
    '/sets/State_Maps?q=Maps'
  );
  expect(screen.getByText(item.set_id)).toBeInTheDocument();
  click('Next');
  await waitFor(() =>
    expect(router.state.location.search).toContain('offset=25')
  );
  expect(await screen.findByText('26–26 of 30')).toBeInTheDocument();
  click('Previous');
  await screen.findByText('1–1 of 30');
  input('Search Sets by title, ID, or legacy code', 'missing');
  fireEvent.submit(screen.getByRole('search'));
  expect(await screen.findByText(/No Sets found/)).toBeInTheDocument();
  expect(router.state.location.search).not.toContain('offset');
});

it('focuses read errors, retries failed reads and hides inaccessible controls', async () => {
  let denied = true;
  setup('/sets', (url) => {
    if (denied) return failed(403);
    return ok(
      url.includes('/admin/contracts/')
        ? { ...contract, create: false }
        : page([])
    );
  });
  await screen.findByRole('alert');
  await waitFor(() => expect(screen.getByRole('alert')).toHaveFocus());
  expect(
    screen.queryByRole('link', { name: 'Create Set' })
  ).not.toBeInTheDocument();
  denied = false;
  click('Try again');
  await screen.findByText(/No Sets found/);
  expect(
    screen.queryByRole('link', { name: 'Create Set' })
  ).not.toBeInTheDocument();
});

it('preserves invalid create fields, focuses the summary and safely retries an uncertain save', async () => {
  const writes: RequestInit[] = [];
  setup('/sets/new?source_id=parent', (url, options) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (options?.method === 'POST') {
      writes.push(options);
      if (writes.length === 1)
        return failed(422, [{ loc: ['body', 'title'], msg: 'Title required' }]);
      if (writes.length === 2) throw new Error('Network lost');
      return ok({ ...item, title: 'New Set' });
    }
    if (url.includes('?')) return ok(page([]));
    return ok({ ...item, title: 'New Set' });
  });
  await screen.findByLabelText('Title (required)');
  await waitFor(() =>
    expect(screen.getByRole('heading', { name: 'Create Set' })).toHaveFocus()
  );
  input('Set ID (optional)', 'State_Maps');
  input('Description', 'Draft description');
  click('Save Set');
  await screen.findByRole('alert');
  await waitFor(() => expect(screen.getByRole('alert')).toHaveFocus());
  expect(screen.getByLabelText('Title (required)')).toHaveAttribute(
    'aria-invalid',
    'true'
  );
  expect(screen.getByLabelText('Description')).toHaveValue('Draft description');
  input('Title (required)', 'New Set');
  click('Save Set');
  await screen.findByText(/API could not be reached/);
  click('Save Set');
  await screen.findByRole('heading', { name: 'New Set' });
  expect(writes[1].body).toBe(writes[2].body);
  expect(writes[1].headers).toEqual(writes[2].headers);
});

it('compares stale edits, preserves only edited fields on rebase, and clears optional values', async () => {
  let current = item;
  let conflict = true;
  const writes: RequestInit[] = [];
  setup('/sets/State_Maps/edit', (url, options) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (options?.method === 'PATCH') {
      writes.push(options);
      if (conflict) {
        conflict = false;
        current = {
          ...item,
          title: 'Someone else',
          description: 'Updated by colleague',
          lock_version: 2,
        };
        return failed(409, {
          code: 'stale_version',
          message: 'Set changed',
        });
      }
      current = {
        ...current,
        ...JSON.parse(String(options.body)),
        lock_version: 3,
      };
      return ok(current);
    }
    return ok(current);
  });
  await screen.findByLabelText('Title (required)');
  input('Title (required)', 'My edit');
  input('Endpoint URL', '');
  input('Staff-only notes', '');
  click('Save Set');
  await screen.findByText('Set changed');
  click('Load latest for comparison');
  await screen.findByText('Review saved version 2');
  expect(screen.getByText(/Saved: Someone else/)).toBeInTheDocument();
  click('Keep my changes on latest version');
  expect(screen.getByLabelText('Description')).toHaveValue(
    'Updated by colleague'
  );
  click('Save Set');
  await screen.findByText('Set saved.');
  expect(JSON.parse(String(writes[1].body))).toEqual({
    title: 'My edit',
    endpoint_url: null,
    admin_notes: '',
    lock_version: 2,
  });
  expect(screen.queryByLabelText('Set ID (optional)')).not.toBeInTheDocument();
});

it('recovers from failed comparison and can discard a conflicting draft', async () => {
  let read = 0;
  setup('/sets/State_Maps/edit', (url, options) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (options?.method)
      return failed(409, { code: 'stale_version', message: 'Set changed' });
    read++;
    if (read === 2) throw new Error('offline');
    return ok({ ...item, lock_version: read === 1 ? 1 : 2 });
  });
  await screen.findByLabelText('Title (required)');
  input('Title (required)', 'Draft');
  click('Save Set');
  await screen.findByText('Set changed');
  click('Load latest for comparison');
  await screen.findByText(/API could not be reached/);
  expect(screen.getByLabelText('Title (required)')).toHaveValue('Draft');
  click('Load latest for comparison');
  await screen.findByText('Review saved version 2');
  click('Discard my changes and use latest');
  expect(screen.getByLabelText('Title (required)')).toHaveValue(item.title);
  expect(screen.getByRole('button', { name: 'Save Set' })).toBeDisabled();
});

it('denies direct create/edit routes and guards dirty navigation', async () => {
  const { router } = setup('/sets/State_Maps/edit', (url) =>
    ok(
      url.includes('/admin/contracts/')
        ? contract
        : url.includes('?')
          ? page([])
          : item
    )
  );
  await screen.findByLabelText('Title (required)');
  input('Title (required)', 'Unsaved');
  fireEvent.click(screen.getByRole('link', { name: 'Back to Sets' }));
  expect(
    await screen.findByRole('heading', { name: 'Discard unsaved changes?' })
  ).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Keep editing' })).toHaveFocus();
  click('Keep editing');
  expect(screen.getByLabelText('Title (required)')).toHaveValue('Unsaved');
  fireEvent.click(screen.getByRole('link', { name: 'Back to Sets' }));
  click('Discard changes');
  await screen.findByRole('heading', { name: 'Sets' });
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      ok(
        url.includes('/admin/contracts/')
          ? { ...contract, create: false, update: false }
          : url.includes('/activity')
            ? page([])
            : item
      )
    )
  );
  await act(() => router.navigate('/sets/new'));
  await screen.findByText('You do not have permission to create Sets.');
  expect(screen.getByRole('button', { name: 'Save Set' })).toBeDisabled();
  await act(() => router.navigate('/sets/State_Maps/edit'));
  await screen.findByText('You do not have permission to edit Sets.');
});

it('preserves the parent Source filter through searching, paging, and creation', async () => {
  const { router } = setup('/sets?source_id=parent', (url) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    const query = new URL(url, 'http://local').searchParams;
    return ok(page([item], Number(query.get('offset')), 30));
  });
  await screen.findByRole('link', { name: item.title });
  expect(screen.getByRole('link', { name: 'Create Set' })).toHaveAttribute(
    'href',
    '/sets/new?source_id=parent'
  );
  input('Search Sets by title, ID, or legacy code', '05a-01');
  fireEvent.submit(screen.getByRole('search'));
  await screen.findByRole('link', { name: item.title });
  click('Next');
  await waitFor(() =>
    expect(router.state.location.search).toContain('offset=25')
  );
  expect(router.state.location.search).toContain('source_id=parent');
  expect(router.state.location.search).toContain('q=05a-01');
});

it('shows the parent and protected Set history, including empty and restricted states', async () => {
  let entries: unknown[] = [
    {
      id: 'entry',
      action: 'set.created',
      outcome: 'succeeded',
      actor_display_name: 'Staff',
      occurred_at: item.updated_at,
      details: { fields: ['title'] },
    },
    {
      id: 'assignment',
      action: 'resource.associated',
      outcome: 'succeeded',
      actor_display_name: 'Cataloger',
      occurred_at: item.updated_at,
      resource_id: 'county/map',
      reason: 'County collection',
      details: { source_set_id: null },
    },
  ];
  let access = true;
  const { router } = setup('/sets/State_Maps', (url) => {
    if (url.includes('/admin/contracts/'))
      return ok({ ...contract, activity_read: access, workflow_read: true });
    if (url.includes('/activity')) return ok(page(entries));
    return ok(item);
  });
  await screen.findByText('Set created');
  fireEvent.click(screen.getByText('Resource assigned to Set'));
  expect(screen.getByText('Resource ID: county/map')).toBeVisible();
  expect(screen.getByText('County collection')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Workflows' })).toHaveAttribute(
    'href',
    '/sets/State_Maps/workflows'
  );
  for (const name of ['Work Queue', 'Maintenance']) {
    expect(screen.queryByRole('link', { name })).not.toBeInTheDocument();
  }
  expect(screen.getByRole('link', { name: 'parent' })).toHaveAttribute(
    'href',
    '/sources/parent'
  );
  expect(screen.getByText('Staff context')).toBeInTheDocument();
  expect(screen.getByText('py_umedia')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Edit Set' })).toHaveAttribute(
    'href',
    '/sets/State_Maps/edit'
  );
  entries = [];
  await act(() => router.navigate('/sets/other'));
  await screen.findByText('No Set history.');
  access = false;
  await act(() => router.navigate('/sets/third'));
  await screen.findByText('Set history requires additional access.');
});

it('selects an existing Source, uses API status choices, and saves the Source-owned Set', async () => {
  const { fetch, router } = setup('/sets/new', (url, options) => {
    if (url.includes('/admin/contracts/'))
      return ok({ ...contract, activity_read: false });
    if (url.startsWith('/api/v1/admin/sources?'))
      return ok(page([{ source_id: 'parent', title: 'Parent portal' }]));
    if (options?.method === 'POST') return ok(item);
    return ok(item);
  });
  await screen.findByLabelText('Title (required)');
  click('Choose Source');
  click(
    await screen
      .findByRole('button', { name: 'Parent portal — parent' })
      .then((button) => button.textContent!)
  );
  input('Title (required)', 'Maps');
  input('Status', 'inactive');
  click('Save Set');
  await waitFor(() =>
    expect(router.state.location.pathname).toBe('/sets/State_Maps')
  );
  const sent = fetch.mock.calls.find(
    ([, options]) => options?.method === 'POST'
  )![1]!;
  expect(JSON.parse(String(sent.body))).toMatchObject({
    source_id: 'parent',
    title: 'Maps',
    status: 'inactive',
  });
  await screen.findByRole('heading', { name: item.title });
});
