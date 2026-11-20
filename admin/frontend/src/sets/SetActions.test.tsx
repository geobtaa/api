import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { SetActions } from './SetActions';
import type { SetRecord, SetContract } from './api';

afterEach(() => vi.unstubAllGlobals());
const item = {
  set_id: 'set-1',
  title: 'County maps',
  status: 'active',
  lock_version: 3,
} as SetRecord;
const contract: SetContract = {
  update: true,
  create: true,
  activity_read: true,
  fields: {},
  state_actions: [
    { current: 'active', target: 'inactive', label: 'Deactivate Set' },
    { current: 'active', target: 'retired', label: 'Retire Set' },
  ],
};
const preview = {
  set_id: 'set-1',
  title: 'County maps',
  current: 'active',
  target: 'inactive',
  lock_version: 3,
  open_tasks: 0,
  can_proceed: true,
  consequences: ['Future recurring Tasks pause.', 'History is preserved.'],
};
const ok = (value: unknown) => ({ ok: true, json: async () => value });
function setup(
  handler: (url: string, options?: RequestInit) => unknown,
  access = contract
) {
  const fetch = vi.fn(async (url: string, options?: RequestInit) =>
    handler(url, options)
  );
  vi.stubGlobal('fetch', fetch);
  const changed = vi.fn();
  const router = createMemoryRouter([
    {
      path: '/',
      element: <SetActions item={item} contract={access} changed={changed} />,
    },
    { path: '/other', element: <p>Other page</p> },
  ]);
  render(<RouterProvider router={router} />);
  return { fetch, changed, router };
}
function click(name: string | RegExp) {
  fireEvent.click(screen.getByRole('button', { name }));
}
async function open(action = 'Deactivate Set') {
  click(/Change state/);
  click(action);
  await screen.findByRole('heading', {
    name: 'Review state change for County maps',
  });
}
function confirm(reason = 'Seasonal maintenance') {
  fireEvent.change(screen.getByLabelText('Reason (required)'), {
    target: { value: reason },
  });
  fireEvent.click(screen.getByLabelText('I confirm this Set state change.'));
  click('Confirm state change');
}

it('requires a preview, reason and confirmation before committing the versioned state', async () => {
  const { fetch, changed } = setup((_, options) =>
    ok(options?.method ? item : preview)
  );
  await open();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Future recurring Tasks pause.')).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Confirm state change' })
  ).toBeDisabled();
  confirm();
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  expect(fetch.mock.calls[1][0]).toBe('/api/v1/admin/sets/set-1/state');
  expect(fetch.mock.calls[1][1]?.method).toBe('PUT');
  expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({
    target: 'inactive',
    lock_version: 3,
    reason: 'Seasonal maintenance',
    confirmed: true,
  });
});

it('blocks retirement for unfinished work and refreshes without losing the reason', async () => {
  let blocked = true;
  const { fetch } = setup(() =>
    ok({
      ...preview,
      target: 'retired',
      can_proceed: !blocked,
      open_tasks: blocked ? 2 : 0,
    })
  );
  await open('Retire Set');
  expect(screen.getByRole('alert')).toHaveTextContent('2 unfinished Task(s)');
  confirm('Closing this source');
  expect(fetch).toHaveBeenCalledTimes(1);
  blocked = false;
  click('Refresh preview');
  await screen.findByLabelText('Reason (required)');
  expect(screen.getByLabelText('Reason (required)')).toHaveValue(
    'Closing this source'
  );
  expect(
    screen.getByLabelText('I confirm this Set state change.')
  ).not.toBeChecked();
  expect(
    screen.getByRole('button', { name: 'Confirm state change' })
  ).toBeDisabled();
  click('Cancel state change');
  expect(screen.queryByLabelText('Reason (required)')).not.toBeInTheDocument();
});

it('reuses the receipt after an uncertain response and focuses recoverable errors', async () => {
  let attempts = 0;
  const { fetch, changed } = setup((_, options) => {
    if (!options?.method) return ok(preview);
    if (++attempts === 1) throw new Error('Connection interrupted');
    return ok(item);
  });
  await open();
  confirm();
  const alert = await screen.findByRole('alert');
  expect(alert).toHaveFocus();
  expect(changed).not.toHaveBeenCalled();
  click('Confirm state change');
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  const writes = fetch.mock.calls.filter(([, options]) => options?.method);
  expect(writes[0][1]?.headers).toEqual(writes[1][1]?.headers);
  expect(writes[0][1]?.body).toEqual(writes[1][1]?.body);
});

it('refreshes a stale version and requires a new confirmation before retrying', async () => {
  let version = 3;
  const { fetch, changed } = setup((_, options) => {
    if (!options?.method) return ok({ ...preview, lock_version: version });
    if (version === 3)
      return {
        ok: false,
        status: 409,
        json: async () => ({
          detail: {
            code: 'stale_version',
            message: 'Set changed. Refresh the state preview.',
          },
        }),
      };
    return ok(item);
  });
  await open();
  confirm();
  await screen.findByRole('alert');
  version = 4;
  click('Refresh preview');
  await screen.findByLabelText('Reason (required)');
  expect(screen.getByLabelText('Reason (required)')).toHaveValue(
    'Seasonal maintenance'
  );
  expect(
    screen.getByLabelText('I confirm this Set state change.')
  ).not.toBeChecked();
  fireEvent.click(screen.getByLabelText('I confirm this Set state change.'));
  click('Confirm state change');
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  const writes = fetch.mock.calls.filter(([, options]) => options?.method);
  expect(JSON.parse(String(writes[1][1]?.body)).lock_version).toBe(4);
  expect(writes[0][1]?.headers).not.toEqual(writes[1][1]?.headers);
});

it('protects a drafted reason when navigating away', async () => {
  const { router } = setup(() => ok(preview));
  await open();
  fireEvent.change(screen.getByLabelText('Reason (required)'), {
    target: { value: 'Retain this reason' },
  });
  await act(() => router.navigate('/other'));
  expect(await screen.findByRole('dialog')).toBeInTheDocument();
  click('Keep editing');
  expect(screen.getByLabelText('Reason (required)')).toHaveValue(
    'Retain this reason'
  );
  await act(() => router.navigate('/other'));
  click('Discard changes');
  expect(await screen.findByText('Other page')).toBeInTheDocument();
});

it('offers import entry points and uses server-provided state permissions', () => {
  setup(() => ok(preview), { ...contract, update: false, state_actions: [] });
  click(/Change state/);
  expect(
    screen.getByText('No state changes are available.')
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Retire Set' })
  ).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Import CSV' })).toHaveAttribute(
    'href',
    '/resources/csv?set_id=set-1'
  );
  click(/More import options/);
  expect(
    screen.getByRole('link', { name: 'Import Distribution links' })
  ).toHaveAttribute('href', '/resources/csv/distributions?set_id=set-1');
  expect(
    screen.queryByRole('link', { name: 'Configure workflow' })
  ).not.toBeInTheDocument();
});
