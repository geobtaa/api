import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ResourceCsv } from './ResourceCsv';
import { ResourceList } from './ResourcePages';
const managingSet = {
  set_id: 'source-1',
  title: 'Fixture collection',
  status: 'active',
};
const row = {
  row: 1,
  resource_id: 'map/1',
  outcome: 'update',
  errors: [],
  warnings: ['Draft only'],
  clear_fields: ['schema_provider_s'],
  changes: { schema_provider_s: { before: 'Provider', after: null } },
};
const preview = {
  preview_hash: 'a'.repeat(64),
  ready: 1,
  items: [
    row,
    {
      ...row,
      row: 2,
      resource_id: 'invalid',
      outcome: 'invalid',
      errors: ['Bad value'],
      changes: {},
      clear_fields: [],
    },
  ],
};
const ok = (data: unknown) => ({ ok: true, json: async () => data });
function setup(url = '/resources/csv?set_id=source-1') {
  const fetch = vi.fn(async (url: string) =>
    url.includes('sets')
      ? ok({ items: [managingSet] })
      : url.endsWith('preview')
        ? ok(preview)
        : ok({ ...preview, items: [{ ...row, outcome: 'updated' }] })
  );
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter initialEntries={[url]}>
      <ResourceCsv />
    </MemoryRouter>
  );
  return fetch;
}
async function prepare() {
  await screen.findByRole('option', { name: 'Fixture collection' });
  fireEvent.change(screen.getByLabelText('CSV text'), {
    target: { value: 'id,lock_version\nmap/1,1' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }));
  await screen.findByRole('heading', { name: 'Preview changes' });
}
beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:report');
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());
it('previews exact changes and applies only after confirmation, with a downloadable report', async () => {
  const fetch = setup();
  expect(screen.queryByLabelText('Import mode')).not.toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'Unassigned drafts' })
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/an empty cell clears the field/i)
  ).toBeInTheDocument();
  expect(screen.queryByText(/companion __clear/)).not.toBeInTheDocument();
  await prepare();
  expect(screen.getByText('Bad value')).toBeInTheDocument();
  expect(
    screen.getByText('Fields to clear: schema_provider_s')
  ).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Apply 1 ready row' })
  ).toBeEnabled();
  expect(
    await screen.findByRole('link', { name: 'Download row report' })
  ).toHaveAttribute('download', 'csv-outcomes.csv');
  fireEvent.click(screen.getByRole('button', { name: 'Apply 1 ready row' }));
  await screen.findByRole('heading', { name: 'Import results' });
  const call = fetch.mock.calls.find((call) => call[0].endsWith('/import'))!;
  expect(
    JSON.parse((call as unknown as [string, RequestInit])[1].body as string)
  ).toMatchObject({
    confirmed: true,
    set_id: 'source-1',
    preview_hash: preview.preview_hash,
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Start another CSV import' })
  );
  expect(screen.queryByLabelText('Import mode')).not.toBeInTheDocument();
  expect(
    screen.queryByRole('heading', { name: 'Import results' })
  ).not.toBeInTheDocument();
});
it('retains input and idempotency key after uncertain commit, and invalidates preview on edits', async () => {
  const fetch = setup();
  await prepare();
  fetch.mockImplementationOnce(async () => {
    throw new Error('offline');
  });
  fireEvent.click(screen.getByRole('button', { name: 'Apply 1 ready row' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Apply 1 ready row' }));
  await screen.findByRole('heading', { name: 'Import results' });
  const calls = fetch.mock.calls.filter((call) =>
    call[0].endsWith('/import')
  ) as unknown as [string, RequestInit][];
  expect(calls[0][1].headers).toEqual(calls[1][1].headers);
  fireEvent.click(
    screen.getByRole('button', { name: 'Start another CSV import' })
  );
  await prepare();
  fireEvent.change(screen.getByLabelText('Set'), {
    target: { value: '' },
  });
  expect(
    screen.queryByRole('heading', { name: 'Preview changes' })
  ).not.toBeInTheDocument();
});

it('previews an uploaded file before staff choose a managing Set', async () => {
  const fetch = setup('/resources/csv');
  const csv = 'ID,Title\nmap/1,New map';
  await screen.findByRole('option', { name: 'Fixture collection' });
  fireEvent.change(screen.getByLabelText('CSV file'), {
    target: { files: [{ text: async () => csv }] },
  });
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Preview CSV' })).toBeEnabled()
  );
  fetch.mockImplementationOnce(async () =>
    ok({ ...preview, ready: 1, items: [{ ...row, outcome: 'create' }] })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }));
  expect(
    await screen.findByRole('button', { name: 'Apply 1 ready row' })
  ).toBeEnabled();
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/admin/resources/csv/preview',
    expect.objectContaining({ body: JSON.stringify({ csv }) })
  );
  fireEvent.change(screen.getByLabelText('Set'), {
    target: { value: 'source-1' },
  });
  expect(
    screen.queryByRole('heading', { name: 'Preview changes' })
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText('CSV text')).toHaveValue(csv);
});
it('accepts a CSV file and reports unreadable files', async () => {
  setup();
  await screen.findByRole('option', { name: 'Fixture collection' });
  const input = screen.getByLabelText('CSV file');
  fireEvent.change(input, {
    target: { files: [{ size: 20, text: async () => 'id\nmap/1' }] },
  });
  await waitFor(() =>
    expect(screen.getByLabelText('CSV text')).toHaveValue('id\nmap/1')
  );
  fireEvent.change(input, {
    target: {
      files: [
        {
          size: 10,
          text: async () => {
            throw Error();
          },
        },
      ],
    },
  });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'could not be read'
  );
  fireEvent.change(input, { target: { files: [] } });
});
it('reports Set loading failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  render(
    <MemoryRouter>
      <ResourceCsv />
    </MemoryRouter>
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Could not load Sets'
  );
});
it('exports all filtered results or selected IDs and clears selection on page changes', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.includes('sets/')
        ? ok(managingSet)
        : ok({
            items: [
              {
                id: 'map/1',
                set_id: 'source-1',
                publication_state: 'draft',
                metadata: { dct_title_s: 'Map' },
              },
            ],
            total: 2,
            offset: 0,
            limit: 1,
          })
    )
  );
  render(
    <MemoryRouter initialEntries={['/resources?set_id=source-1&q=Map']}>
      <ResourceList />
    </MemoryRouter>
  );
  await screen.findByRole('link', { name: 'Map' });
  expect(
    screen.getByRole('link', { name: 'Export filtered CSV' })
  ).toHaveAttribute(
    'href',
    '/api/v1/admin/resources/csv/export?set_id=source-1&q=Map&format=geomg'
  );
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select map/1' }));
  expect(
    screen.getByRole('link', { name: 'Export selected CSV' })
  ).toHaveAttribute(
    'href',
    '/api/v1/admin/resources/csv/export?format=geomg&ids=map%2F1&q=Map&set_id=source-1'
  );
  fireEvent.click(
    screen.getByRole('checkbox', { name: 'Select all Resources on this page' })
  );
  expect(
    screen.queryByRole('link', { name: 'Export selected CSV' })
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('checkbox', { name: 'Select all Resources on this page' })
  );
  fireEvent.click(screen.getAllByRole('button', { name: 'Next' })[0]);
  await screen.findByRole('link', { name: 'Map' });
  expect(
    screen.queryByRole('link', { name: 'Export selected CSV' })
  ).not.toBeInTheDocument();
});

it('accepts a large file and pages 10,000 outcomes while retaining the full report', async () => {
  const fetch = setup();
  await screen.findByRole('option', { name: 'Fixture collection' });
  const source = 'id,dct_title_s\n' + 'x,Long title\n'.repeat(10000);
  fireEvent.change(screen.getByLabelText('CSV file'), {
    target: { files: [{ size: 20_000_000, text: async () => source }] },
  });
  await waitFor(() =>
    expect(screen.getByLabelText('CSV text')).toHaveValue(source)
  );
  fetch.mockImplementationOnce(async () =>
    ok({
      ...preview,
      ready: 10000,
      items: Array.from({ length: 10000 }, (_, i) => ({
        ...row,
        row: i + 1,
        resource_id: `large-${i}`,
        outcome: i === 9999 ? 'invalid' : 'update',
      })),
    })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }));
  await screen.findByText('10000 matching rows · Page 1 of 100');
  expect(screen.getAllByRole('row')).toHaveLength(101);
  fireEvent.click(screen.getByRole('button', { name: 'Next rows' }));
  expect(screen.getByText('large-100')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Previous rows' }));
  fireEvent.change(screen.getByLabelText('Show outcomes'), {
    target: { value: 'invalid' },
  });
  expect(screen.getByText('large-9999')).toBeInTheDocument();
  expect(screen.getAllByRole('row')).toHaveLength(2);
  expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
});

it('opens results on page one with all outcomes after applying a filtered preview', async () => {
  const fetch = setup();
  await screen.findByRole('option', { name: 'Fixture collection' });
  const updates = Array.from({ length: 101 }, (_, index) => ({
    ...row,
    row: index + 1,
    resource_id: `map-${index + 1}`,
  }));
  const invalid = { ...preview.items[1], row: 102 };
  fetch.mockResolvedValueOnce(
    ok({ ...preview, ready: 101, items: [...updates, invalid] })
  );
  await prepare();
  fireEvent.change(screen.getByLabelText('Show outcomes'), {
    target: { value: 'update' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Next rows' }));
  expect(
    screen.getByText('101 matching rows · Page 2 of 2')
  ).toBeInTheDocument();

  fetch.mockResolvedValueOnce(
    ok({
      ...preview,
      ready: 101,
      items: [
        ...updates.map((item) => ({ ...item, outcome: 'updated' })),
        invalid,
      ],
    })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Apply 101 ready rows' }));
  await screen.findByRole('heading', { name: 'Import results' });
  expect(screen.getByLabelText('Show outcomes')).toHaveValue('all');
  expect(
    screen.getByText('102 matching rows · Page 1 of 2')
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'map-1' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Next rows' }));
  expect(screen.getByText('Bad value')).toBeInTheDocument();
});

it.each(['sources', 'sets'] as const)(
  'previews and applies a catalog upload from %s',
  async (entity) => {
    const report = {
      ...preview,
      items: [{ ...row, resource_id: undefined, record_id: 'Campus' }],
    };
    const fetch = vi.fn(async () => ok(report));
    vi.stubGlobal('fetch', fetch);
    render(
      <MemoryRouter>
        <ResourceCsv entity={entity} />
      </MemoryRouter>
    );
    expect(screen.queryByLabelText('Set')).not.toBeInTheDocument();
    expect(screen.getByText('Export for editing')).toHaveAttribute(
      'href',
      '/api/v1/admin/' + entity + '/csv/export'
    );
    fireEvent.change(screen.getByLabelText('Import mode'), {
      target: { value: 'create' },
    });
    fireEvent.change(screen.getByLabelText('CSV text'), {
      target: { value: 'source_id,title\nCampus,Campus' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }));
    expect(await screen.findByText('Campus')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Apply 1 ready row' }));
    await screen.findByRole('heading', { name: 'Import results' });
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/admin/' + entity + '/csv/import',
      expect.objectContaining({
        body: expect.stringContaining('"mode":"create"'),
      })
    );
  }
);

it('defaults Distribution uploads to Add links and previews explicit replacement across Sets', async () => {
  const fetch = vi.fn(async (url: string) =>
    url.includes('sets?')
      ? ok({ items: [] })
      : ok({
          ...preview,
          items: [{ ...row, input_rows: [1, 2], set_id: 'County' }],
        })
  );
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <ResourceCsv entity="distributions" />
    </MemoryRouter>
  );
  expect(screen.getByLabelText('Import mode')).toHaveValue('add_links');
  fireEvent.change(screen.getByLabelText('Import mode'), {
    target: { value: 'replace_links' },
  });
  fireEvent.change(screen.getByLabelText('CSV text'), {
    target: {
      value:
        'friendlier_id,reference_type,distribution_url,label\nmap/1,download,https://example.org/a,A',
    },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }));
  await screen.findByRole('heading', { name: 'Preview changes' });
  expect(screen.getByText('County · 1')).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Apply 1 ready Resource group' })
  ).toBeEnabled();
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/admin/resources/csv/preview',
    expect.objectContaining({
      body: expect.stringContaining('"mode":"replace_links"'),
    })
  );
});

it('includes Set choices beyond the first catalog page', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      ok({
        items: [
          url.includes('offset=1')
            ? { ...managingSet, set_id: 'next', title: 'Later Set' }
            : managingSet,
        ],
        total: 2,
      })
    )
  );
  render(
    <MemoryRouter>
      <ResourceCsv />
    </MemoryRouter>
  );
  expect(
    await screen.findByRole('option', { name: 'Later Set' })
  ).toBeInTheDocument();
});

it('shows both mixed import outcomes and links to the affected Resources and saved upload', async () => {
  const fetch = setup('/resources/csv');
  await screen.findByRole('option', { name: 'Fixture collection' });
  fetch.mockImplementationOnce(async () =>
    ok({
      ...preview,
      ready: 2,
      items: [
        row,
        { ...row, row: 2, resource_id: 'new-map', outcome: 'create' },
      ],
    })
  );
  await prepare();
  fetch.mockImplementationOnce(async () =>
    ok({
      ready: 2,
      preview_hash: preview.preview_hash,
      batch_id: 'mixed-batch',
      items: [
        { ...row, outcome: 'updated' },
        { ...row, row: 2, resource_id: 'new-map', outcome: 'created' },
      ],
    })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Apply 2 ready rows' }));
  await screen.findByRole('heading', { name: 'Import results' });
  expect(screen.getByRole('status')).toHaveTextContent('updated 1 · created 1');
  expect(screen.getByRole('link', { name: 'map/1' })).toHaveAttribute(
    'href',
    '/resources/~bWFwLzE'
  );
  expect(screen.getByRole('link', { name: 'new-map' })).toHaveAttribute(
    'href',
    '/resources/new-map'
  );
  expect(
    screen.getByRole('link', { name: 'View saved upload' })
  ).toHaveAttribute('href', '/resources/csv/intake/mixed-batch');
});

it('shows a missing-column error and withdraws the apply action for the rejected file', async () => {
  const fetch = setup();
  await prepare();
  fetch.mockImplementationOnce(async () => ({
    ok: false,
    status: 422,
    json: async () => ({
      detail: {
        code: 'invalid_csv',
        message: 'Incomplete Resource CSV template. Missing columns: Provider.',
      },
    }),
  }));
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Missing columns: Provider'
  );
  expect(
    screen.queryByRole('button', { name: /Apply .* ready/ })
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText('CSV text')).toHaveValue(
    'id,lock_version\nmap/1,1'
  );
});
