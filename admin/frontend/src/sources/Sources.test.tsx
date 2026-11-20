import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { SourceList } from './SourceBrowse';
import { SourcePage } from './SourceEditor';
import type { Source } from './api';

const item: Source = {
  source_id: 'State_Maps',
  legacy_code: '20d-0006',
  title: 'State Maps',
  description: 'Maps and imagery',
  landing_page: 'https://example.org/maps',
  admin_notes: 'Staff context',
  lock_version: 1,
  updated_at: '2026-09-21T12:00:00Z',
};
const contract = {
  create: true,
  update: true,
  activity_read: true,
  resource_read: true,
  fields: {
    source_id: { maxLength: 128 },
    title: { maxLength: 250 },
    description: { maxLength: 5000 },
    landing_page: {},
    admin_notes: { maxLength: 10000 },
    legacy_code: { maxLength: 128 },
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
      : handler(url, options)
  );
  vi.stubGlobal('fetch', fetch);
  const router = createMemoryRouter(
    [
      { path: '/sources', element: <SourceList /> },
      { path: '/sources/new', element: <SourcePage mode="create" /> },
      {
        path: '/sources/:sourceId/edit',
        element: <SourcePage mode="edit" />,
      },
      { path: '/sources/:sourceId', element: <SourcePage /> },
      { path: '/resources', element: <h1>Resource results</h1> },
      { path: '/resources/:resourceId', element: <h1>Resource detail</h1> },
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

it('browses Sources with URL search, pagination, stable IDs and return context', async () => {
  const { router } = setup('/sources?q=Maps', (url) => {
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
    '/sources/State_Maps?q=Maps'
  );
  expect(screen.getByText(item.source_id)).toBeInTheDocument();
  expect(screen.getByText('20d-0006')).toBeInTheDocument();
  click('Next');
  await waitFor(() =>
    expect(router.state.location.search).toContain('offset=25')
  );
  expect(await screen.findByText('26–26 of 30')).toBeInTheDocument();
  click('Previous');
  await screen.findByText('1–1 of 30');
  input('Search Sources by title, ID, or legacy code', 'missing');
  fireEvent.submit(screen.getByRole('search'));
  expect(await screen.findByText(/No Sources found/)).toBeInTheDocument();
  expect(router.state.location.search).not.toContain('offset');
});

it('focuses read errors, retries failed reads and hides inaccessible controls', async () => {
  let denied = true;
  setup('/sources', (url) => {
    if (denied) return failed(403);
    return ok(
      url.includes('/admin/contracts/')
        ? { ...contract, create: false }
        : page([])
    );
  });
  await waitFor(() => expect(screen.getByRole('alert')).toHaveFocus());
  expect(
    screen.queryByRole('link', { name: 'Create Source' })
  ).not.toBeInTheDocument();
  denied = false;
  click('Try again');
  await screen.findByText(/No Sources found/);
  expect(
    screen.queryByRole('link', { name: 'Create Source' })
  ).not.toBeInTheDocument();
});

it('renders protected history and scoped Resources with direct navigation', async () => {
  const { fetch, router } = setup('/sources/State_Maps?q=Maps', (url) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (url.includes('/activity'))
      return ok(
        page(
          [
            {
              id: 'event',
              action: 'review.completed',
              outcome: 'succeeded',
              actor_display_name: 'Steward',
              occurred_at: item.updated_at,
              reason: 'Reviewed metadata',
              details: {},
            },
          ],
          url.includes('offset=25') ? 25 : 0,
          30
        )
      );
    if (url.startsWith('/api/v1/admin/resources'))
      return ok(
        page([{ id: 'map/1', metadata: { dct_title_s: 'First map' } }])
      );
    return ok(item);
  });
  await screen.findByRole('heading', { name: item.title });
  expect(screen.getByText('20d-0006')).toBeInTheDocument();
  expect(screen.getByText('Staff context')).toBeInTheDocument();
  await screen.findByText('Reviewed metadata');
  fireEvent.click(screen.getByRole('tab', { name: 'Browse Resources' }));
  await screen.findByRole('link', { name: 'First map' });
  fireEvent.click(screen.getByRole('tab', { name: 'Activity Log' }));
  expect(
    fetch.mock.calls.some(([url]) => url.includes('filters=%7B%22source%22'))
  ).toBe(true);
  fireEvent.click(
    within(
      screen.getByRole('navigation', { name: 'Source history pages' })
    ).getByText('Next')
  );
  await screen.findByText('26–26 of 30');
  expect(screen.getByRole('link', { name: 'Back to Sources' })).toHaveAttribute(
    'href',
    '/sources?q=Maps'
  );
  fireEvent.click(screen.getByRole('tab', { name: 'Browse Resources' }));
  fireEvent.click(
    screen.getByRole('link', { name: 'Browse associated Resources' })
  );
  await screen.findByRole('heading', { name: 'Resource results' });
  expect(new URLSearchParams(router.state.location.search).get('filters')).toBe(
    '{"source":["State_Maps"]}'
  );
});

it('supports empty detail sections and separates history/resource grants', async () => {
  const { router } = setup('/sources/State_Maps', (url) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (url.includes('?')) return ok(page([]));
    return ok({
      ...item,
      description: '',
      admin_notes: '',
      landing_page: null,
    });
  });
  await screen.findByText('No Source history.');
  await screen.findByText('No associated Resources within your access.');
  expect(screen.getByText('No landing page.')).toBeInTheDocument();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      ok(
        url.includes('/admin/contracts/')
          ? {
              ...contract,
              update: false,
              activity_read: false,
              resource_read: false,
            }
          : item
      )
    )
  );
  await act(() => router.navigate('/sources/other'));
  await screen.findByText('Source history requires additional access.');
  expect(
    screen.queryByRole('link', { name: 'Edit Source' })
  ).not.toBeInTheDocument();
});

it('preserves invalid create fields, focuses the summary and safely retries an uncertain save', async () => {
  const writes: RequestInit[] = [];
  setup('/sources/new', (url, options) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (options?.method === 'POST') {
      writes.push(options);
      if (writes.length === 1)
        return failed(422, [{ loc: ['body', 'title'], msg: 'Title required' }]);
      if (writes.length === 2) throw new Error('Network lost');
      return ok({ ...item, title: 'New Source' });
    }
    if (url.includes('?')) return ok(page([]));
    return ok({ ...item, title: 'New Source' });
  });
  await screen.findByLabelText('Title (required)');
  expect(screen.getByRole('heading', { name: 'Create Source' })).toHaveFocus();
  input('Source ID (optional)', 'State_Maps');
  input('Description', 'Draft description');
  click('Save Source');
  expect(await screen.findByRole('alert')).toHaveFocus();
  expect(screen.getByLabelText('Title (required)')).toHaveAttribute(
    'aria-invalid',
    'true'
  );
  expect(screen.getByLabelText('Description')).toHaveValue('Draft description');
  input('Title (required)', 'New Source');
  click('Save Source');
  await screen.findByText(/API could not be reached/);
  click('Save Source');
  await screen.findByRole('heading', { name: 'New Source' });
  expect(writes[1].body).toBe(writes[2].body);
  expect(writes[1].headers).toEqual(writes[2].headers);
});

it('compares stale edits, preserves only edited fields on rebase, and clears optional values', async () => {
  let current = item;
  let conflict = true;
  const writes: RequestInit[] = [];
  setup('/sources/State_Maps/edit', (url, options) => {
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
          message: 'Source changed',
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
  input('Landing page', '');
  input('Staff-only notes', '');
  click('Save Source');
  await screen.findByText('Source changed');
  click('Load latest for comparison');
  await screen.findByText('Review saved version 2');
  expect(screen.getByText(/Saved: Someone else/)).toBeInTheDocument();
  click('Keep my changes on latest version');
  expect(screen.getByLabelText('Description')).toHaveValue(
    'Updated by colleague'
  );
  click('Save Source');
  await screen.findByText('Source saved.');
  expect(JSON.parse(String(writes[1].body))).toEqual({
    title: 'My edit',
    landing_page: null,
    admin_notes: '',
    lock_version: 2,
  });
  expect(
    screen.queryByLabelText('Source ID (optional)')
  ).not.toBeInTheDocument();
});

it('recovers from failed comparison and can discard a conflicting draft', async () => {
  let read = 0;
  setup('/sources/State_Maps/edit', (url, options) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (options?.method)
      return failed(409, { code: 'stale_version', message: 'Source changed' });
    read++;
    if (read === 2) throw new Error('offline');
    return ok({ ...item, lock_version: read === 1 ? 1 : 2 });
  });
  await screen.findByLabelText('Title (required)');
  input('Title (required)', 'Draft');
  click('Save Source');
  await screen.findByText('Source changed');
  click('Load latest for comparison');
  await screen.findByText(/API could not be reached/);
  expect(screen.getByLabelText('Title (required)')).toHaveValue('Draft');
  click('Load latest for comparison');
  await screen.findByText('Review saved version 2');
  click('Discard my changes and use latest');
  expect(screen.getByLabelText('Title (required)')).toHaveValue(item.title);
  expect(screen.getByRole('button', { name: 'Save Source' })).toBeDisabled();
});

it('denies direct create/edit routes and guards dirty navigation', async () => {
  const { router } = setup('/sources/State_Maps/edit', (url) =>
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
  fireEvent.click(screen.getByRole('link', { name: 'Back to Sources' }));
  expect(
    await screen.findByRole('heading', { name: 'Discard unsaved changes?' })
  ).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Keep editing' })).toHaveFocus();
  click('Keep editing');
  expect(screen.getByLabelText('Title (required)')).toHaveValue('Unsaved');
  fireEvent.click(screen.getByRole('link', { name: 'Back to Sources' }));
  click('Discard changes');
  await screen.findByRole('heading', { name: 'Sources' });
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
  await act(() => router.navigate('/sources/new'));
  await screen.findByText('You do not have permission to create Sources.');
  expect(screen.getByRole('button', { name: 'Save Source' })).toBeDisabled();
  await act(() => router.navigate('/sources/State_Maps/edit'));
  await screen.findByText('You do not have permission to edit Sources.');
});

it('searches within the Source, resets pagination and retains filters in Resource navigation', async () => {
  const { fetch } = setup('/sources/State_Maps', (url) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (url.includes('/activity')) return ok(page([]));
    if (url.startsWith('/api/v1/admin/resources')) {
      const query = new URL(url, 'https://local').searchParams;
      return ok(
        page(
          query.get('q') === 'missing'
            ? []
            : [
                {
                  id: 'map/1',
                  set_id: 'life-1',
                  set_title: 'Map maintenance',
                  publication_state: 'draft',
                  metadata: {
                    dct_title_s: 'First map',
                    gbl_resourceClass_sm: ['Maps'],
                  },
                },
              ],
          Number(query.get('offset')),
          query.get('q') === 'missing' ? 0 : 30
        )
      );
    }
    return ok(item);
  });
  fireEvent.click(await screen.findByRole('tab', { name: 'Browse Resources' }));
  await screen.findByText('30 associated Resources');
  expect(screen.getByRole('link', { name: 'Map maintenance' })).toHaveAttribute(
    'href',
    '/sets/life-1'
  );
  expect(screen.getByText('draft')).toBeInTheDocument();
  expect(
    screen.getByText('Staff context').closest('details')
  ).not.toHaveAttribute('open');
  expect(screen.getByRole('link', { name: /Visit website/ })).toHaveAttribute(
    'rel',
    'noreferrer'
  );
  fireEvent.click(
    within(
      screen.getByRole('navigation', { name: 'Associated Resource pages' })
    ).getByText('Next')
  );
  await screen.findByText('26–26 of 30');
  input('Search within this Source', 'missing');
  fireEvent.submit(
    screen.getByRole('search', { name: 'Associated Resources' })
  );
  await screen.findByText(/No Resources match this search/);
  const searched = fetch.mock.calls
    .map(([url]) => url)
    .find((url) => url.includes('q=missing'))!;
  expect(new URL(searched, 'https://local').searchParams.get('offset')).toBe(
    '0'
  );
  expect(new URL(searched, 'https://local').searchParams.get('filters')).toBe(
    '{"source":["State_Maps"]}'
  );
  click('Clear search');
  fireEvent.click(await screen.findByRole('tab', { name: 'Browse Resources' }));
  await screen.findByText('30 associated Resources');
  input('Search within this Source', 'map');
  click('Search Resources');
  await screen.findByText('30 matching Resources');
  expect(
    screen.getByRole('link', { name: 'First map' }).getAttribute('href')
  ).toContain('q=map');
});

it('links a Source to its filtered Set browser only with Set access', async () => {
  let canReadSets = true;
  const { router } = setup('/sources/State_Maps', (url) => {
    if (url.includes('/admin/contracts/'))
      return ok({
        ...contract,
        set_read: canReadSets,
        activity_read: false,
        resource_read: false,
      });
    return ok(item);
  });
  expect(
    await screen.findByRole('link', { name: 'Browse Sets for this Source' })
  ).toHaveAttribute('href', '/sets?source_id=State_Maps');
  canReadSets = false;
  await act(() => router.navigate('/sources/Other'));
  await screen.findByRole('heading', { name: item.title });
  expect(
    screen.queryByRole('link', { name: 'Browse Sets for this Source' })
  ).not.toBeInTheDocument();
});

it('edits the Source legacy code independently of staff notes', async () => {
  const writes: RequestInit[] = [];
  setup('/sources/State_Maps/edit', (url, options) => {
    if (url.includes('/admin/contracts/')) return ok(contract);
    if (options?.method === 'PATCH') {
      writes.push(options);
      return ok({ ...item, legacy_code: '20d-0007', lock_version: 2 });
    }
    return ok(item);
  });
  fireEvent.change(await screen.findByLabelText('Legacy code'), {
    target: { value: '20d-0007' },
  });
  click('Save Source');
  await screen.findByText('Source saved.');
  expect(JSON.parse(String(writes[0].body))).toEqual({
    legacy_code: '20d-0007',
    lock_version: 1,
  });
});
