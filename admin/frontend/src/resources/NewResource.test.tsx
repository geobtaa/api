import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';
import { resourcePath } from '../urlIds';

const base = '/api/v1/admin/resources';
const ok = (value: unknown) => ({ ok: true, json: async () => value });

function open(path: string, canCreate = true, failFirst = false) {
  const writes: RequestInit[] = [];
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/contracts/resources'))
      return ok({
        can_create: canCreate,
        can_choose_set: true,
        fields: [],
        sections: ['Description'],
        distribution_types: [],
      });
    if (init?.method === 'POST') {
      writes.push(init);
      if (failFirst && writes.length === 1) throw new Error('offline');
      return ok({ id: 'new' });
    }
    if (url.includes('/sets?'))
      return ok({
        total: 2,
        items: [
          { set_id: 'maps', title: 'County Maps', status: 'active' },
          { set_id: 'old', title: 'Retired maps', status: 'retired' },
        ],
      });
    if (url.endsWith('/sets/maps')) return ok({ title: 'County Maps' });
    if (url === base + '/~bmV3')
      return ok({
        id: 'new',
        metadata: { dct_title_s: 'Atlas' },
        publication_state: 'draft',
        lock_version: 1,
        distributions: [],
        source_record: null,
        import_warnings: [],
      });
    if (url.includes('/facets')) return ok([]);
    return ok({
      can_create: canCreate,
      items: [],
      total: 0,
      offset: 0,
      limit: 25,
    });
  });
  vi.stubGlobal('fetch', fetch);
  const router = createMemoryRouter([{ path: '*', element: <App /> }], {
    initialEntries: [path],
  });
  render(<RouterProvider router={router} />);
  return { router, writes };
}
afterEach(() => vi.unstubAllGlobals());

it.each([false, true])(
  'creates a draft from Resources with Set scope %s',
  async (assigned) => {
    const { router, writes } = open(
      assigned ? '/resources?set_id=maps' : '/resources',
      true,
      !assigned
    );
    fireEvent.click(await screen.findByRole('link', { name: 'New Resource' }));
    const input = await screen.findByRole('textbox', {
      name: 'Resource ID (required)',
    });
    expect(input).toBeRequired();
    await screen.findByRole('option', { name: 'County Maps (maps)' });
    expect(
      screen.queryByRole('option', { name: /Retired maps/ })
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText('Managing Set (optional)')).toHaveValue(
      assigned ? 'maps' : ''
    );
    fireEvent.change(input, { target: { value: 'new' } });
    fireEvent.change(screen.getByLabelText('Title (required)'), {
      target: { value: 'Atlas' },
    });
    fireEvent.change(screen.getByLabelText('Description'), {
      target: { value: 'Historic maps' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }));
    if (!assigned) {
      expect(await screen.findByRole('alert')).toHaveFocus();
      expect(input).toHaveValue('new');
      fireEvent.click(screen.getByRole('button', { name: 'Create draft' }));
      await waitFor(() => expect(writes).toHaveLength(2));
      expect(writes[1].headers).toEqual(writes[0].headers);
    }
    expect(await screen.findByRole('heading', { name: 'Atlas' })).toBeVisible();
    expect(router.state.location.pathname).toBe(resourcePath('new'));
    expect(JSON.parse(String(writes[0].body))).toEqual({
      id: 'new',
      title: 'Atlas',
      description: 'Historic maps',
      set_id: assigned ? 'maps' : null,
    });
    expect(
      screen.queryByText('Import evidence and warnings')
    ).not.toBeInTheDocument();
  }
);

it('preserves a draft when navigation is cancelled and permits clearing the initial Set', async () => {
  open('/resources/new?set_id=maps');
  await screen.findByRole('option', { name: 'County Maps (maps)' });
  fireEvent.change(screen.getByLabelText('Managing Set (optional)'), {
    target: { value: '' },
  });
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'County map' },
  });
  fireEvent.click(screen.getByRole('link', { name: '← Resources' }));
  expect(await screen.findByRole('dialog')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByLabelText('Title (required)')).toHaveValue('County map');
  expect(screen.getByLabelText('Managing Set (optional)')).toHaveValue('');
});

it('hides creation for a read-only user and explains a direct visit', async () => {
  const { router } = open('/resources', false);
  await screen.findByText(/0 Resources · 0 selected/);
  expect(
    screen.queryByRole('link', { name: 'New Resource' })
  ).not.toBeInTheDocument();
  await act(() => router.navigate('/resources/new'));
  await screen.findByText('Resource creation permission is required.');
  expect(
    screen.queryByRole('button', { name: 'Create draft' })
  ).not.toBeInTheDocument();
});
