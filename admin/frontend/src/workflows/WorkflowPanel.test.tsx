import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkflowPanel } from './WorkflowPanel';

const base = '/api/v1/admin/workflows';
const process = (name = 'Review', position = 1) => ({
  position,
  process_type: 'review',
  name,
  configuration_schema_version: 1,
  configuration: {},
});
const version = (number = 1, state = 'draft', entries = [process()]) => ({
  version_id: `v${number}`,
  number,
  state,
  checksum: state === 'draft' ? null : 'abc123',
  processes: entries,
});
const initial = {
  workflow_id: 'one',
  title: 'County Workflow',
  lock_version: 1,
  active: null as ReturnType<typeof version> | null,
  draft: version() as ReturnType<typeof version> | null,
  can_change: true,
  can_activate: true,
};
const contract = {
  process_types: [
    {
      key: 'review',
      label: 'Review',
      definition: 'Review candidates.',
      configuration_fields: [],
    },
    {
      key: 'harvest',
      label: 'Harvest',
      definition: 'Acquire candidates.',
      configuration_fields: ['endpoint_url'],
    },
  ],
  configuration_schema: {
    properties: { endpoint_url: { title: 'Endpoint override' } },
  },
  maximum_processes: 100,
  configuration_schema_version: 1,
  can_create: true,
};
const response = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status });
function setup(overrides: Partial<typeof initial> = {}) {
  const state = {
    item: { ...initial, ...overrides },
    failures: [] as (Error | Response)[],
    readFailure: null as Error | null,
    historyFailure: false,
  };
  const fetch = vi.fn(
    async (url: string, options?: RequestInit): Promise<Response> => {
      if (options?.method) {
        const failure = state.failures.shift();
        if (failure instanceof Error) throw failure;
        if (failure) return failure;
        const body = JSON.parse(String(options.body));
        const next = {
          ...state.item,
          lock_version: state.item.lock_version + 1,
        };
        if (url === base) {
          next.title = body.title;
          next.draft = version(1, 'draft', []);
        } else if (url.endsWith('/activate')) {
          next.active = { ...next.draft!, state: 'active', checksum: 'abc123' };
          next.draft = null;
        } else if (options.method === 'PUT') {
          next.draft = { ...next.draft!, processes: body.processes };
        } else {
          next.draft = version(2, 'draft', next.active!.processes);
        }
        state.item = next;
        return response(next);
      }
      if (state.readFailure) {
        const error = state.readFailure;
        state.readFailure = null;
        throw error;
      }
      if (url.includes('/admin/contracts/')) return response(contract);
      if (url.includes('/versions?')) {
        if (state.historyFailure) {
          state.historyFailure = false;
          throw new Error('offline');
        }
        return response({
          items: [version(1, 'superseded')],
          total: 6,
          offset: url.includes('offset=5') ? 5 : 0,
          limit: 5,
        });
      }
      if (url.startsWith(base + '?'))
        return response({
          items: [state.item],
          total: 21,
          offset: url.includes('offset=20') ? 20 : 0,
          limit: 20,
        });
      return response(state.item);
    }
  );
  vi.stubGlobal('fetch', fetch);
  const changed = vi.fn();
  const dirty = vi.fn();
  const busy = vi.fn();
  render(
    <WorkflowPanel
      setId="life"
      retired={false}
      disabled={false}
      onChanged={changed}
      onDirty={dirty}
      onBusy={busy}
    />
  );
  return { state, fetch, changed, dirty };
}
async function openExisting() {
  fireEvent.click(screen.getByRole('button', { name: 'Show Workflows' }));
  fireEvent.change(await screen.findByLabelText('Workflow'), {
    target: { value: 'one' },
  });
  await screen.findByLabelText('Process 1 name');
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('creates, edits structured processes, orders, activates and clones a Workflow', async () => {
  const { fetch, changed, dirty } = setup();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Show Workflows' }));
  fireEvent.change(await screen.findByLabelText('New Workflow title'), {
    target: { value: 'New source flow' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Create Workflow draft' })
  );
  await screen.findByText(/New source flow · version/);
  fireEvent.click(screen.getByRole('button', { name: 'Add process' }));
  fireEvent.change(screen.getByLabelText('Process 1 type'), {
    target: { value: 'harvest' },
  });
  fireEvent.change(screen.getByLabelText('Process 1 name'), {
    target: { value: 'Fetch source' },
  });
  fireEvent.change(screen.getByLabelText('Endpoint override for process 1'), {
    target: { value: 'https://example.org' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Add process' }));
  fireEvent.click(screen.getByRole('button', { name: 'Move process 2 up' }));
  expect(screen.getByLabelText('Process 1 name')).toHaveValue('Review');
  fireEvent.click(screen.getByRole('button', { name: 'Move process 1 down' }));
  expect(screen.getByRole('button', { name: 'Hide Workflows' })).toBeDisabled();
  expect(dirty).toHaveBeenLastCalledWith(true);
  fireEvent.click(screen.getByRole('button', { name: 'Save Workflow draft' }));
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Save Workflow draft' })
    ).toBeDisabled()
  );
  const update = fetch.mock.calls.find(([, opts]) => opts?.method === 'PUT')!;
  expect(
    JSON.parse(String(update[1]!.body)).processes.map(
      (p: { position: number }) => p.position
    )
  ).toEqual([1, 2]);
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: 'Activate saved draft' }));
  await screen.findByRole('button', { name: 'Clone active version to draft' });
  expect(
    screen.queryByRole('button', { name: 'Save Workflow draft' })
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Clone active version to draft' })
  );
  await screen.findByText('Draft definition 2');
  fireEvent.click(screen.getByRole('button', { name: 'Remove process 2' }));
  expect(screen.queryByLabelText('Process 2 name')).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Discard Workflow edits' })
  );
  expect(screen.getByLabelText('Process 2 name')).toHaveValue('Review');
  expect(changed).toHaveBeenCalledTimes(4);
});

it('preserves uncertain writes and reuses the request key', async () => {
  const { fetch, state } = setup();
  await openExisting();
  fireEvent.change(screen.getByLabelText('Process 1 name'), {
    target: { value: 'Local review' },
  });
  state.failures.push(new Error('offline'));
  fireEvent.click(screen.getByRole('button', { name: 'Save Workflow draft' }));
  expect(await screen.findByRole('alert')).toHaveFocus();
  expect(screen.getByLabelText('Process 1 name')).toHaveValue('Local review');
  fireEvent.click(screen.getByRole('button', { name: 'Save Workflow draft' }));
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Save Workflow draft' })
    ).toBeDisabled()
  );
  const writes = fetch.mock.calls.filter(([, opts]) => opts?.method === 'PUT');
  expect(writes).toHaveLength(2);
  expect(
    (writes[0][1]!.headers as Record<string, string>)['Idempotency-Key']
  ).toBe((writes[1][1]!.headers as Record<string, string>)['Idempotency-Key']);
});

it('compares a stale draft and preserves local changes until explicit rebase or discard', async () => {
  const { state } = setup();
  await openExisting();
  fireEvent.change(screen.getByLabelText('Process 1 name'), {
    target: { value: 'My review' },
  });
  state.failures.push(
    response(
      { detail: { code: 'stale_version', message: 'Workflow changed.' } },
      409
    )
  );
  state.item = {
    ...state.item,
    lock_version: 2,
    draft: version(1, 'draft', [process('Saved review')]),
  };
  fireEvent.click(screen.getByRole('button', { name: 'Save Workflow draft' }));
  await screen.findByRole('alert');
  expect(
    screen.getByRole('button', { name: 'Save Workflow draft' })
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Load saved Workflow for comparison' })
  );
  await screen.findByText('Saved review');
  expect(screen.getByLabelText('Process 1 name')).toHaveValue('My review');
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Keep my draft against the latest version',
    })
  );
  expect(
    screen.getByRole('button', { name: 'Save Workflow draft' })
  ).toBeEnabled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Discard Workflow edits' })
  );
  expect(screen.getByLabelText('Process 1 name')).toHaveValue('Saved review');
});

it('shows read-only definitions and paginated history with recovery', async () => {
  const { state, fetch } = setup({ can_change: false, can_activate: false });
  await openExisting();
  expect(screen.getByLabelText('Process 1 name')).toBeDisabled();
  expect(
    screen.queryByRole('button', { name: 'Save Workflow draft' })
  ).not.toBeInTheDocument();
  state.historyFailure = true;
  fireEvent.click(screen.getByRole('button', { name: 'Show version history' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Show version history' }));
  await screen.findByText('Version history');
  fireEvent.click(screen.getByRole('button', { name: 'Older versions' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('offset=5'),
      expect.anything()
    )
  );
  fireEvent.click(screen.getByRole('button', { name: 'Newer versions' }));
  fireEvent.click(screen.getByRole('button', { name: 'Next Workflows' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('offset=20'),
      expect.anything()
    )
  );
  fireEvent.click(screen.getByRole('button', { name: 'Previous Workflows' }));
});

it('retries failed initial reads and can discard a new title', async () => {
  const { state } = setup();
  state.readFailure = new Error('offline');
  fireEvent.click(screen.getByRole('button', { name: 'Show Workflows' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Retry Workflows' }));
  fireEvent.change(await screen.findByLabelText('New Workflow title'), {
    target: { value: 'Unsaved' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Discard new Workflow' }));
  expect(screen.getByLabelText('New Workflow title')).toHaveValue('');
  fireEvent.click(screen.getByRole('button', { name: 'Hide Workflows' }));
  expect(screen.queryByLabelText('Workflow')).not.toBeInTheDocument();
});
