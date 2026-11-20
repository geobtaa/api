import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { IntakeQueue } from './IntakeQueue';
import { ResourceCsv } from './ResourceCsv';

const base = '/api/v1/admin/resources/csv/intake';
const drafts = [1, 2].map((row_number) => ({
  row_number,
  resource_id: 'map-' + row_number,
  title: 'Map ' + row_number,
  version: 1,
  csv: 'ID,Title\nmap-' + row_number + ',Map ' + row_number,
}));
function setup(path = '/resources/csv/intake') {
  URL.createObjectURL = vi.fn(() => 'blob:receipt');
  URL.revokeObjectURL = vi.fn();
  let pending = [...drafts];
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : {};
    const items = pending
      .filter((d) => !body.rows || body.rows.includes(d.row_number))
      .map((d) => ({
        row: d.row_number,
        resource_id: d.resource_id,
        outcome: url.endsWith('/preview') ? 'create' : 'created',
        errors: [],
        changes: {},
        clear_fields: [],
        warnings: [],
      }));
    let data: unknown;
    if (url.includes('/admin/sets?'))
      data = {
        items: [{ set_id: 's', title: 'Maps', status: 'active' }],
        total: 1,
      };
    else if (url.startsWith(base + '?'))
      data = [
        {
          id: 'batch',
          created_at: '2026-11-19T15:00:00Z',
          uploader: 'Karen',
          pending: 2,
        },
      ];
    else if (url.includes('/rows/')) {
      pending = pending.map((d) =>
        d.row_number === 2 ? { ...d, title: 'Revised map', csv: body.csv } : d
      );
      data = pending[1];
    } else if (url.includes('/assignments') || url.endsWith('/receipt')) {
      data = { items, preview_hash: 'a'.repeat(64), ready: items.length };
      if (url.endsWith('/assignments'))
        pending = pending.filter(
          (d) => !items.some((r) => r.row === d.row_number)
        );
    } else data = { items: pending, pending: pending.length };
    return { ok: true, json: async () => data };
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/resources/csv/intake/:batchId?"
          element={<IntakeQueue />}
        />
      </Routes>
    </MemoryRouter>
  );
  return fetch;
}
afterEach(() => vi.unstubAllGlobals());
it('reopens an upload and assigns one draft, then all remaining drafts', async () => {
  const fetch = setup();
  await screen.findByText('Karen');
  fireEvent.click(screen.getByRole('link', { name: /2026/ }));
  await screen.findByText('2 unassigned drafts in this upload');
  expect(
    screen.queryByLabelText('Optional destination Set')
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Assign to a Set…' }));
  fireEvent.click(screen.getByRole('button', { name: 'View upload receipt' }));
  await screen.findByText('Original upload receipt');
  fireEvent.click(screen.getByRole('button', { name: 'Hide upload receipt' }));
  await screen.findByRole('option', { name: 'Maps (s)' });
  fireEvent.change(screen.getByLabelText('Optional destination Set'), {
    target: { value: 's' },
  });
  fireEvent.click(screen.getByLabelText('Select map-1'));
  fireEvent.click(screen.getByRole('button', { name: 'Preview assignment' }));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Assign 1 draft to Set' })
  );
  await screen.findByText('1 unassigned draft in this upload');
  expect(fetch).toHaveBeenCalledWith(
    base + '/batch/assignments',
    expect.objectContaining({
      body: JSON.stringify({
        set_id: 's',
        rows: [1],
        confirmed: true,
        preview_hash: 'a'.repeat(64),
      }),
    })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Edit row 2' }));
  fireEvent.change(screen.getByLabelText('Draft CSV for row 2'), {
    target: { value: 'ID,Title\nmap-2,Revised map' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save draft edits' }));
  await screen.findByText('Revised map');
  fireEvent.click(
    screen.getByLabelText('Select all 1 pending draft in this upload')
  );
  fireEvent.click(screen.getByRole('button', { name: 'Preview assignment' }));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Assign 1 draft to Set' })
  );
  await screen.findByText('0 unassigned drafts in this upload');
  expect(fetch).toHaveBeenCalledWith(
    base + '/batch/assignments/preview',
    expect.objectContaining({
      body: JSON.stringify({ set_id: 's', rows: null }),
    })
  );
});
it('clears a preview when selection changes', async () => {
  setup('/resources/csv/intake/batch');
  await screen.findByText('2 unassigned drafts in this upload');
  expect(
    screen.queryByLabelText('Optional destination Set')
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Assign to a Set…' }));
  fireEvent.click(screen.getByRole('button', { name: 'Edit row 1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel edit' }));
  await screen.findByRole('option', { name: 'Maps (s)' });
  fireEvent.change(screen.getByLabelText('Optional destination Set'), {
    target: { value: 's' },
  });
  fireEvent.click(screen.getByLabelText('Select map-1'));
  fireEvent.click(screen.getByRole('button', { name: 'Preview assignment' }));
  await screen.findByText('Assignment preview');
  fireEvent.click(screen.getByLabelText('Select map-2'));
  await waitFor(() =>
    expect(screen.queryByText('Assignment preview')).not.toBeInTheDocument()
  );
});

it('opens the saved upload and exposes catalog records immediately without a Set prompt', async () => {
  URL.createObjectURL = vi.fn(() => 'blob:report');
  URL.revokeObjectURL = vi.fn();
  const report = {
    ready: 1,
    preview_hash: 'a'.repeat(64),
    items: [
      {
        row: 1,
        resource_id: 'map-1',
        outcome: 'create',
        errors: [],
        warnings: [],
        clear_fields: [],
        changes: {},
      },
    ],
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const data = url.includes('/sets?')
        ? { total: 0, items: [] }
        : url.endsWith('/preview')
          ? report
          : url.endsWith('/import')
            ? {
                ...report,
                items: [{ ...report.items[0], outcome: 'created' }],
                batch_id: 'saved-upload',
              }
            : { pending: 1, items: [{ ...drafts[0], catalog_id: 'map-1' }] };
      return { ok: true, json: async () => data };
    })
  );
  render(
    <MemoryRouter initialEntries={['/resources/csv']}>
      <Routes>
        <Route path="/resources/csv" element={<ResourceCsv />} />
        <Route
          path="/resources/csv/intake/:batchId"
          element={<IntakeQueue />}
        />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByLabelText('CSV text'), {
    target: { value: 'ID,Title\nmap-1,Map 1' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Preview CSV' }));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Apply 1 ready row' })
  );
  await screen.findByText('Upload saved.');
  expect(await screen.findByRole('link', { name: 'Map 1' })).toHaveAttribute(
    'href',
    '/resources/map-1'
  );
  expect(screen.getByRole('link', { name: 'View Resource' })).toHaveAttribute(
    'href',
    '/resources/map-1'
  );
  expect(
    screen.queryByLabelText('Optional destination Set')
  ).not.toBeInTheDocument();
});
