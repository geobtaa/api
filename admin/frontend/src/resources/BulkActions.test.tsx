import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';
import contract from './editor.contract.fixture.json';

const base = '/api/v1/admin/resource-bulk-actions';
const ok = (data: unknown) => ({ ok: true, json: async () => data });
function setup(path: string, allowed = true) {
  const posts: {
    url: string;
    body: unknown;
    headers: HeadersInit | undefined;
  }[] = [];
  const applied = new Set<string>();
  function summary(id: string) {
    return {
      id,
      selection_id: 'saved',
      reverts: id === 'undo' ? 'edit' : null,
      actor_name: 'Staff member',
      created_at: '2026-11-19T14:00:00Z',
      applied_at: applied.has(id) ? '2026-11-19T15:00:00Z' : null,
      applied_by: applied.has(id) ? 'Staff member' : null,
      field_labels: {
        dct_publisher_sm: 'Publishers',
        schema_provider_s: 'Provider',
      },
    };
  }
  let failPreview = true;
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'POST' || options?.method === 'PUT') {
      posts.push({
        url,
        body: options.body ? JSON.parse(String(options.body)) : null,
        headers: options.headers,
      });
      if (url.endsWith('/selections')) {
        const { ids } = JSON.parse(String(options.body));
        return ok(
          ids
            ? { selection_id: 'checked', total: ids.length }
            : { selection_id: 'saved', total: 30 }
        );
      }
      if (url === base) {
        if (failPreview) {
          failPreview = false;
          throw new Error('offline');
        }
        return ok({ id: 'edit' });
      }
      if (url.endsWith('/reversions')) return ok({ id: 'undo' });
      const id = url.split('/').at(-2)!;
      applied.add(id);
      return ok({ id });
    }
    if (url.includes('/contracts/resources'))
      return ok({ ...contract, can_bulk_edit: allowed });
    if (url.startsWith(base + '?'))
      return ok({ items: [summary('edit')], total: 1, offset: 0, limit: 25 });
    if (url.startsWith(base + '/')) {
      const id = url.slice(base.length + 1).split('?')[0];
      const status = applied.has(id) ? 'changed' : 'ready';
      return ok({
        ...summary(id),
        items: [
          {
            resource_id: 'map/1',
            before_version: id === 'undo' ? 2 : 1,
            after_version: applied.has(id) ? 2 : null,
            status,
            changes: {
              schema_provider_s: {
                before: id === 'undo' ? 'New provider' : null,
                after: id === 'undo' ? null : 'New provider',
              },
            },
          },
        ],
        totals: { [status]: 30 },
        total: 30,
        offset: Number(
          new URL(url, 'https://local').searchParams.get('offset')
        ),
        limit: 25,
      });
    }
    if (url.includes('facets')) return ok([]);
    return ok({
      can_select: true,
      can_bulk_edit: allowed,
      items: ['map/1', 'map/2', 'map/3'].map((id) => ({
        id,
        metadata: { dct_title_s: id },
        publication_state: 'draft',
      })),
      total: 30,
      offset: 0,
      limit: 25,
    });
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <RouterProvider
      router={createMemoryRouter([{ path: '*', element: <App /> }], {
        initialEntries: [path],
      })}
    />
  );
  return { posts, fetch };
}
afterEach(() => vi.unstubAllGlobals());

it('snapshots the filtered results, previews multiple fields, confirms, and reverts from history', async () => {
  const filters = JSON.stringify({ provider: ['Old provider'] });
  const { posts, fetch } = setup(
    '/resources?' + new URLSearchParams({ q: 'maps', filters })
  );
  fireEvent.click(
    await screen.findByRole('checkbox', { name: 'Select map/1' })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Edit all 30 matches' }));
  expect(posts[0].body).toEqual({
    q: 'maps',
    set_id: null,
    filters: JSON.parse(filters),
  });
  const fields = await screen.findByLabelText('Add a field');
  fireEvent.change(fields, { target: { value: 'dct_publisher_sm' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add publishers' }));
  fireEvent.change(screen.getByLabelText('Publishers 1'), {
    target: { value: 'Library' },
  });
  fireEvent.change(fields, { target: { value: 'schema_provider_s' } });
  fireEvent.change(screen.getByLabelText('New provider'), {
    target: { value: 'New provider' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Preview changes' }));
  expect(await screen.findByRole('alert')).toHaveFocus();
  fireEvent.click(screen.getByRole('button', { name: 'Preview changes' }));
  expect(
    await screen.findByRole('heading', { name: 'Preview bulk edit' })
  ).toBeVisible();
  expect(posts[1].headers).toEqual(posts[2].headers);
  expect(posts[2].body).toEqual({
    selection_id: 'saved',
    values: {
      dct_publisher_sm: ['Library'],
      schema_provider_s: 'New provider',
    },
    clear_fields: [],
  });
  expect(screen.getByText('Before: Not supplied')).toBeVisible();
  expect(screen.getByRole('link', { name: 'map/1' })).toHaveAttribute(
    'href',
    '/resources/~bWFwLzE'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('offset=25'),
      expect.anything()
    )
  );
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Confirm changes to 30 Resources',
    })
  );
  expect(await screen.findByText('After: New provider')).toBeVisible();
  fireEvent.click(screen.getByRole('link', { name: '← My bulk actions' }));
  fireEvent.click(await screen.findByRole('link', { name: /Edit ·/ }));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Preview revert' })
  );
  expect(
    await screen.findByRole('heading', { name: 'Preview revert' })
  ).toBeVisible();
  expect(screen.getByText('Proposed: Not supplied')).toBeVisible();
  fireEvent.click(
    screen.getByRole('button', { name: 'Confirm revert for 30 Resources' })
  );
  expect(await screen.findByText('After: Not supplied')).toBeVisible();
  expect(
    posts.filter((p) => p.url.endsWith('/confirmation')).map((p) => p.body)
  ).toEqual([{ confirmed: true }, { confirmed: true }]);
});

it('opens a separate bulk edit for exactly the checked rows even after saving all matches', async () => {
  const filters = { provider: ['Old provider'] };
  const { posts } = setup(
    '/resources?' +
      new URLSearchParams({
        q: 'maps',
        set_id: 'county',
        filters: JSON.stringify(filters),
      })
  );
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Select all 30 matching Resources',
    })
  );
  await screen.findByRole('link', { name: 'Review saved selection' });
  expect(
    screen.queryByRole('button', { name: /Edit .* selected/ })
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('checkbox', { name: 'Select all Resources on this page' })
  );
  expect(screen.getByRole('button', { name: 'Edit 3 selected' })).toBeVisible();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select map/2' }));
  fireEvent.click(screen.getByRole('button', { name: 'Edit 2 selected' }));
  expect(
    await screen.findByRole('link', { name: '← Saved selection' })
  ).toHaveAttribute('href', '/resources/selections/checked');
  const criteria = { q: 'maps', set_id: 'county', filters };
  expect(posts.map((p) => p.body)).toEqual([
    criteria,
    { ...criteria, ids: ['map/1', 'map/3'] },
  ]);
});

it('uses a new retry key if the checked IDs change after a failed request', async () => {
  const { fetch } = setup('/resources');
  const one = await screen.findByRole('checkbox', { name: 'Select map/1' });
  fireEvent.click(one);
  fetch.mockRejectedValueOnce(new Error('offline'));
  fireEvent.click(screen.getByRole('button', { name: 'Edit 1 selected' }));
  await screen.findByRole('alert');
  fireEvent.click(one);
  expect(
    screen.queryByRole('button', { name: /Edit .* selected/ })
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select map/2' }));
  fireEvent.click(screen.getByRole('button', { name: 'Edit 1 selected' }));
  await screen.findByRole('heading', { name: 'Bulk edit Resources' });
  const requests = fetch.mock.calls
    .filter(([url]) => url.endsWith('/selections'))
    .map(([, init]) => init!);
  expect(requests.map((req) => JSON.parse(String(req.body)).ids)).toEqual([
    ['map/1'],
    ['map/2'],
  ]);
  expect(new Headers(requests[1].headers).get('Idempotency-Key')).not.toBe(
    new Headers(requests[0].headers).get('Idempotency-Key')
  );
});

it('distinguishes clearing a field from replacing it, and protects unfinished edits', async () => {
  const { posts } = setup('/resources/selections/saved/bulk-edit');
  const fields = await screen.findByLabelText('Add a field');
  fireEvent.change(fields, { target: { value: 'schema_provider_s' } });
  fireEvent.click(screen.getByLabelText('Clear provider'));
  expect(screen.queryByLabelText('New provider')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: '← Saved selection' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Keep editing' }));
  fireEvent.click(screen.getByRole('button', { name: 'Preview changes' }));
  await screen.findByRole('alert');
  expect(posts[0].body).toEqual({
    selection_id: 'saved',
    values: {},
    clear_fields: ['schema_provider_s'],
  });
});
it('denies the editor on a direct visit without bulk permission', async () => {
  setup('/resources/selections/saved/bulk-edit', false);
  expect(
    await screen.findByText('Bulk edit permission is required.')
  ).toBeVisible();
  expect(screen.queryByLabelText('Add a field')).not.toBeInTheDocument();
});
