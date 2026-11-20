import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { createMemoryRouter, Link, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { ResourceEditor, type ResourceDetailData } from './ResourceEditor';
import contract from './editor.contract.fixture.json';

const initial: ResourceDetailData = {
  id: 'map/1',
  source_id: 'parent',
  set_id: 'source',
  set_title: 'Example collection',
  publication_state: 'draft',
  lock_version: 1,
  editable: true,
  metadata: {
    id: 'map/1',
    dct_title_s: 'Original title',
    dct_description_sm: ['Description'],
    schema_provider_s: 'Original provider',
    gbl_resourceClass_sm: ['Maps'],
    gbl_mdVersion_s: 'Aardvark',
    gbl_georeferenced_b: false,
    gbl_indexYear_im: [1900],
  },
  distributions: [
    { distribution_type_id: 7, url: 'https://example.org', label: null },
  ],
  source_record: { id: 'map/1' },
  import_warnings: [],
};
const ok = (data: unknown) => ({ ok: true, json: async () => data });
function setup({
  editable = true,
  published = false,
  projectionStatus = 'pending',
} = {}) {
  let current = {
    ...initial,
    editable,
    publication_state: published ? 'published' : 'draft',
  };
  const saved = vi.fn();
  const patches: RequestInit[] = [];
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.includes('/relationships?')) {
      const offset = Number(
        new URL(url, 'http://localhost').searchParams.get('offset')
      );
      return ok({
        items: [
          {
            relationship: offset ? 'Has part' : 'Is part of',
            id: offset ? 'child' : 'parent',
            title: `${offset ? 'Child' : 'Parent'} map v${current.lock_version}`,
            set_id: 'source',
          },
        ],
        total: 2,
        offset,
        limit: 1,
      });
    }
    if (url.endsWith('/published-edits/preview'))
      return ok({
        preview_id: 'reviewed',
        changes: {
          dct_title_s: { before: 'Original title', after: 'Alpha title' },
        },
      });
    if (url.endsWith('/published-edits'))
      return ok({
        ...current,
        lock_version: 2,
        projection_status: projectionStatus,
      });
    if (options?.method === 'PATCH') {
      patches.push(options);
      const payload = JSON.parse(String(options.body));
      const metadata = { ...current.metadata, ...payload.values };
      for (const name of payload.clear_fields) delete metadata[name];
      current = {
        ...current,
        lock_version: current.lock_version + 1,
        metadata,
        distributions: payload.distributions ?? current.distributions,
      };
      return ok(current);
    }
    return ok(url.endsWith('/contracts/resources') ? contract : current);
  });
  vi.stubGlobal('fetch', fetch);
  const router = createMemoryRouter([
    {
      path: '/',
      element: (
        <>
          <Link to="/elsewhere">Leave editor</Link>
          <ResourceEditor item={current} onSaved={saved} />
        </>
      ),
    },
    { path: '/elsewhere', element: <h1>Elsewhere</h1> },
  ]);
  render(<RouterProvider router={router} />);
  return { fetch, saved, patches, router };
}
afterEach(() => vi.unstubAllGlobals());
async function ready() {
  await screen.findByRole('tab', { name: 'Description' });
}
const tab = (name: string) =>
  fireEvent.click(screen.getByRole('tab', { name }));
it('groups saved relationships with metadata and refreshes them after saving', async () => {
  const { patches } = setup();
  await ready();
  expect(
    screen.queryByRole('region', { name: 'Relationships' })
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'Edited title' },
  });
  tab('Relationships');
  const panel = screen.getByRole('tabpanel', {
    name: 'Relationships',
  });
  expect(
    screen.queryByRole('tab', { name: 'Rights & relationships' })
  ).not.toBeInTheDocument();
  expect(
    within(panel).queryByLabelText('Access rights')
  ).not.toBeInTheDocument();
  fireEvent.click(
    within(panel).getByRole('button', { name: 'Related Resources' })
  );
  fireEvent.change(within(panel).getByLabelText('Related Resources 1'), {
    target: { value: 'related-map' },
  });
  expect(
    await within(panel).findByRole('link', { name: 'Parent map v1' })
  ).toBeVisible();
  fireEvent.click(
    within(panel).getByRole('button', { name: 'Next relationships' })
  );
  expect(
    await within(panel).findByRole('link', { name: 'Child map v1' })
  ).toBeVisible();
  expect(patches).toHaveLength(0);
  expect(screen.getByText('Unsaved changes')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  expect(
    await within(panel).findByRole('link', { name: 'Parent map v2' })
  ).toBeVisible();
  expect(patches).toHaveLength(1);
  expect(JSON.parse(String(patches[0].body)).values.dct_relation_sm).toEqual([
    'related-map',
  ]);
  tab('Rights');
  expect(
    screen.queryByRole('region', { name: 'Relationships' })
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText('Access rights')).toBeVisible();
});

it('keeps saved relationship navigation usable with read-only metadata', async () => {
  setup({ editable: false });
  await ready();
  tab('Relationships');
  expect(
    await screen.findByRole('link', { name: 'Parent map v1' })
  ).toBeVisible();
  const next = screen.getByRole('button', { name: 'Next relationships' });
  expect(next).toBeEnabled();
  fireEvent.click(next);
  expect(
    await screen.findByRole('link', { name: 'Child map v1' })
  ).toBeVisible();
  expect(
    screen.queryByRole('button', { name: 'Save changes' })
  ).not.toBeInTheDocument();
});

it('uses a compact section layout and saves only changed fields', async () => {
  const { patches, saved } = setup();
  await ready();
  expect(screen.getByLabelText('Title (required)')).toHaveValue(
    'Original title'
  );
  expect(screen.queryByLabelText('Provider')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'Edited title' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  expect(await screen.findByText('Saved version 2.')).toBeInTheDocument();
  expect(JSON.parse(String(patches[0].body))).toEqual({
    lock_version: 1,
    values: { dct_title_s: 'Edited title' },
    clear_fields: [],
  });
  expect(saved).toHaveBeenCalled();
});
it('edits repeatable values and explicit clears across sections', async () => {
  const { patches } = setup();
  await ready();
  fireEvent.click(screen.getByRole('button', { name: 'Add descriptions' }));
  fireEvent.change(screen.getByLabelText('Descriptions 2'), {
    target: { value: 'Second description' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Remove Descriptions 1' })
  );
  tab('People & subjects');
  fireEvent.click(screen.getByRole('button', { name: 'Clear Provider' }));
  expect(screen.getByText('This field will be cleared.')).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Undo clear for Provider' })
  );
  expect(screen.getByLabelText('Provider')).toHaveValue('Original provider');
  fireEvent.click(screen.getByRole('button', { name: 'Clear Provider' }));
  tab('Place & time');
  fireEvent.change(screen.getByLabelText('Index years 1'), {
    target: { value: '0' },
  });
  fireEvent.change(screen.getByLabelText('Georeferenced'), {
    target: { value: 'true' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByText('Saved version 2.');
  expect(JSON.parse(String(patches[0].body))).toMatchObject({
    values: {
      dct_description_sm: ['Second description'],
      gbl_indexYear_im: [0],
      gbl_georeferenced_b: true,
    },
    clear_fields: ['schema_provider_s'],
  });
});
it('adds, labels, reorders, and removes structured Distributions', async () => {
  const { patches } = setup();
  await ready();
  tab('Distributions');
  fireEvent.click(screen.getByRole('button', { name: 'Add Distribution' }));
  fireEvent.change(screen.getByLabelText('Type 2'), { target: { value: '8' } });
  fireEvent.change(screen.getByLabelText('URL 2'), {
    target: { value: 'https://example.org/download' },
  });
  fireEvent.change(screen.getByLabelText('Label 2'), {
    target: { value: 'Data' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Move Distribution 2 up' })
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Remove Distribution 2' })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByText('Saved version 2.');
  expect(JSON.parse(String(patches[0].body)).distributions).toEqual([
    {
      distribution_type_id: 8,
      url: 'https://example.org/download',
      label: 'Data',
    },
  ]);
});
it('supports keyboard tab navigation and read-only metadata', async () => {
  setup({ editable: false });
  await ready();
  const first = screen.getByRole('tab', { name: 'Description' });
  fireEvent.keyDown(first, { key: 'ArrowRight' });
  expect(
    screen.getByRole('tab', { name: 'People & subjects' })
  ).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByLabelText('Provider')).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('tab', { name: 'People & subjects' }), {
    key: 'End',
  });
  expect(screen.getByRole('tab', { name: 'Distributions' })).toHaveAttribute(
    'aria-selected',
    'true'
  );
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Distributions' }), {
    key: 'Home',
  });
  fireEvent.keyDown(first, { key: 'ArrowLeft' });
  expect(screen.getByRole('tab', { name: 'Distributions' })).toHaveFocus();
  expect(
    screen.queryByRole('button', { name: 'Save changes' })
  ).not.toBeInTheDocument();
});
it('retains a draft on save failure and reuses its idempotency key', async () => {
  const { fetch } = setup();
  await ready();
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'Draft' },
  });
  fetch.mockRejectedValueOnce(new Error('offline'));
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(screen.getByLabelText('Title (required)')).toHaveValue('Draft');
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByText('Saved version 2.');
  const calls = fetch.mock.calls.filter(
    ([, options]) => options?.method === 'PATCH'
  );
  expect(calls[0][1]?.headers).toEqual(calls[1][1]?.headers);
});
it('compares a stale edit with the latest saved record before retrying', async () => {
  const { fetch, patches } = setup();
  await ready();
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'My draft' },
  });
  fetch.mockResolvedValueOnce({
    ok: false,
    status: 409,
    json: async () => ({
      detail: { code: 'stale_version', message: 'Resource changed' },
    }),
  } as never);
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByRole('alert');
  fetch.mockResolvedValueOnce(
    ok({
      ...initial,
      lock_version: 2,
      metadata: { ...initial.metadata, dct_title_s: 'Another editor' },
    })
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Load latest for comparison' })
  );
  await screen.findByRole('heading', { name: 'Review saved version 2' });
  expect(screen.getByLabelText('Title (required)')).toHaveValue('My draft');
  expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Keep my changes on latest version' })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByText('Saved version 2.');
  expect(JSON.parse(String(patches[0].body)).lock_version).toBe(2);
});
it('can discard a conflicting local draft in favor of the latest record', async () => {
  const { fetch } = setup();
  await ready();
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'Local' },
  });
  fetch.mockResolvedValueOnce({
    ok: false,
    status: 409,
    json: async () => ({
      detail: { code: 'stale_version', message: 'Changed' },
    }),
  } as never);
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await screen.findByRole('alert');
  fetch.mockResolvedValueOnce(
    ok({
      ...initial,
      lock_version: 2,
      metadata: { ...initial.metadata, dct_title_s: 'Server' },
    })
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Load latest for comparison' })
  );
  await screen.findByRole('heading', { name: 'Review saved version 2' });
  fireEvent.click(
    screen.getByRole('button', { name: 'Discard my changes and use latest' })
  );
  expect(screen.getByLabelText('Title (required)')).toHaveValue('Server');
  expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
});
it('protects unsaved changes when leaving the editor', async () => {
  setup();
  await ready();
  fireEvent.change(screen.getByLabelText('Title (required)'), {
    target: { value: 'Draft' },
  });
  fireEvent.click(screen.getByRole('link', { name: 'Leave editor' }));
  await screen.findByRole('dialog');
  fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByLabelText('Title (required)')).toHaveValue('Draft');
  fireEvent.click(screen.getByRole('link', { name: 'Leave editor' }));
  await screen.findByRole('dialog');
  fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
  expect(
    await screen.findByRole('heading', { name: 'Elsewhere' })
  ).toBeInTheDocument();
});
it('recovers from editor contract failure', async () => {
  const { fetch } = setup(); // Replace the pending first response before a fresh mount below.
  await ready();
  await act(async () => {});
  fetch.mockRejectedValueOnce(new Error('offline'));
  const router = createMemoryRouter([
    { path: '/', element: <ResourceEditor item={initial} onSaved={vi.fn()} /> },
  ]);
  render(<RouterProvider router={router} />);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'editor could not be loaded'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Retry editor' }));
  await waitFor(() =>
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  );
});
it('shows nested Distribution validation errors without losing input', async () => {
  const { fetch } = setup();
  await ready();
  tab('Distributions');
  fireEvent.change(screen.getByLabelText('URL 1'), {
    target: { value: 'bad' },
  });
  fetch.mockResolvedValueOnce({
    ok: false,
    status: 422,
    json: async () => ({
      detail: [
        { loc: ['body', 'distributions', 0, 'url'], msg: 'Use an HTTP(S) URL' },
      ],
    }),
  } as never);
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'distributions.0.url: Use an HTTP(S) URL'
  );
  expect(screen.getByLabelText('URL 1')).toHaveValue('bad');
});

it.each([
  ['pending', 'Saved · updating dev2'],
  ['live', 'Live on dev2'],
])(
  'reports the confirmed public revision as %s',
  async (projectionStatus, message) => {
    const { fetch } = setup({ published: true, projectionStatus });
    await ready();
    fireEvent.change(screen.getByLabelText('Title (required)'), {
      target: { value: 'Alpha title' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Preview published changes' })
    );
    expect(
      await screen.findByRole('region', { name: 'Published edit preview' })
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole('button', { name: 'Confirm published changes' })
    );
    expect(await screen.findByText(message)).toBeVisible();
    const submitted = fetch.mock.calls.find(([url]) =>
      url.endsWith('/published-edits')
    );
    expect(JSON.parse(String(submitted?.[1]?.body))).toMatchObject({
      confirmed: true,
      preview_id: 'reviewed',
    });
  }
);
