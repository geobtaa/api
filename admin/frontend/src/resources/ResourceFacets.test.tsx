import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ResourceList, ResourceDetail } from './ResourcePages';
const ok = (data: unknown) => ({ ok: true, json: async () => data });
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
});
afterEach(() => vi.unstubAllGlobals());
it('builds a faceted result set with counts and exports the identical filters', async () => {
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/facets'))
      return ok([{ field: 'provider', label: 'Provider' }]);
    if (url.includes('/facets/provider'))
      return ok({
        items: [
          { value: 'P1', label: 'P1', count: 3 },
          { value: 'P2', label: 'P2', count: 2 },
        ],
        more: true,
        total: 21,
      });
    return ok({
      items: [{ id: 'map', set_id: 'lc', metadata: { dct_title_s: 'Map' } }],
      total: 1,
      offset: 0,
      limit: 25,
    });
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  await screen.findByText('Provider', { selector: 'summary' });
  fireEvent.click(await screen.findByLabelText('P1 (3)'));
  const expected = JSON.stringify({ provider: ['P1'] });
  await waitFor(() =>
    expect(
      screen
        .getByRole('link', { name: 'Export filtered CSV' })
        .getAttribute('href')
    ).toContain(encodeURIComponent(expected))
  );
  expect(
    screen.getByRole('button', { name: 'Remove provider: P1' })
  ).toBeInTheDocument();
  fireEvent.click(await screen.findByLabelText('P2 (2)'));
  await waitFor(() =>
    expect(
      screen.getByRole('link', { name: 'Map' }).getAttribute('href')
    ).toContain(encodeURIComponent(JSON.stringify({ provider: ['P1', 'P2'] })))
  );
  fireEvent.click(screen.getByRole('button', { name: 'More »' }));
  const modal = within(screen.getByRole('dialog'));
  fireEvent.click(await modal.findByRole('button', { name: 'Next' }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => url.includes('offset=10'))).toBe(
      true
    )
  );
  fireEvent.click(await modal.findByRole('button', { name: 'Previous' }));
  fireEvent.change(screen.getByLabelText('Find facet values'), {
    target: { value: 'P1' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => url.includes('term=P1'))).toBe(true)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Close facet options' }));
  fireEvent.click(screen.getByRole('button', { name: 'Remove provider: P1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Clear all' }));
  expect(
    screen.getByRole('link', { name: 'Export filtered CSV' })
  ).toHaveAttribute(
    'href',
    '/api/v1/admin/resources/csv/export?q=&format=geomg'
  );
});
it('retains filters in Resource detail return links', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      ok({
        id: 'map',
        set_id: 'lc',
        metadata: { dct_title_s: 'Map' },
        import_warnings: [],
        source_record: {},
      })
    )
  );
  const filters = JSON.stringify({ provider: ['P1'] });
  render(
    <MemoryRouter
      initialEntries={[`/resources/map?filters=${encodeURIComponent(filters)}`]}
    >
      <ResourceDetail />
    </MemoryRouter>
  );
  expect(
    screen.getByRole('link', { name: '← Resources' }).getAttribute('href')
  ).toContain(encodeURIComponent(filters));
});
it('reports missing facet services and invalid filter URL without crashing', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/facets')) throw Error();
      return ok({ items: [], total: 0, limit: 25 });
    })
  );
  render(
    <MemoryRouter initialEntries={['/resources?filters=null']}>
      <ResourceList />
    </MemoryRouter>
  );
  expect(
    await screen.findByText('Filters unavailable. Reload to retry.')
  ).toBeInTheDocument();
});
it('reports facet value failures and empty searches', async () => {
  let fail = true;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/facets'))
        return ok([{ field: 'provider', label: 'Provider' }]);
      if (url.includes('/facets/provider')) {
        if (fail) throw Error();
        return ok({ items: [], more: false });
      }
      return ok({ items: [], total: 0, limit: 25 });
    })
  );
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  await screen.findByText('Provider', { selector: 'summary' });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Facet values unavailable'
  );
  fail = false;
  fireEvent.click(screen.getByText('Provider', { selector: 'summary' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('group', { name: 'Provider filters' })
    ).not.toBeInTheDocument()
  );
  fireEvent.click(screen.getByText('Provider', { selector: 'summary' }));
  expect(await screen.findByText('No matching values.')).toBeInTheDocument();
});

it('keeps sidebar groups open while browsing and supports collapsing filters on mobile', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.endsWith('/facets')
        ? ok([
            { field: 'provider', label: 'Provider' },
            { field: 'place', label: 'Place' },
          ])
        : url.includes('/facets/')
          ? ok({ items: [], more: false })
          : ok({ items: [], total: 0, limit: 25 })
    )
  );
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  await screen.findByRole('group', { name: 'Provider filters' });
  fireEvent.click(screen.getByText('Place', { selector: 'summary' }));
  expect(
    screen.getByRole('group', { name: 'Place filters' })
  ).toBeInTheDocument();
  fireEvent.pointerDown(document.body);
  expect(
    screen.getByRole('group', { name: 'Provider filters' })
  ).toBeInTheDocument();
  fireEvent.click(screen.getByText('Provider', { selector: 'summary' }));
  await waitFor(() =>
    expect(
      screen.queryByRole('group', { name: 'Provider filters' })
    ).not.toBeInTheDocument()
  );
  expect(
    screen.getByRole('group', { name: 'Place filters' })
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Show filters' }));
  expect(screen.getByRole('button', { name: 'Hide filters' })).toHaveAttribute(
    'aria-expanded',
    'true'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Hide filters' }));
  expect(screen.getByRole('button', { name: 'Show filters' })).toHaveAttribute(
    'aria-expanded',
    'false'
  );
});

it('switches include/exclude, supports all, and retains selections in exports', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.endsWith('/facets'))
        return ok([{ field: 'provider', label: 'Provider' }]);
      if (url.includes('/facets/provider'))
        return ok({
          items: [
            { value: 'P1', label: 'P1', count: 3 },
            { value: 'P2', label: 'P2', count: 2 },
          ],
          more: false,
        });
      return ok({
        items: [{ id: 'map', set_id: 'lc', metadata: { dct_title_s: 'Map' } }],
        total: 1,
        offset: 0,
        limit: 25,
      });
    })
  );
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  fireEvent.click(await screen.findByRole('button', { name: 'P1 (3)' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Exclude P1' }));
  expect(await screen.findByRole('button', { name: 'P1 (3)' })).toHaveAttribute(
    'aria-pressed',
    'false'
  );
  expect(
    await screen.findByRole('button', { name: 'Exclude P1' })
  ).toHaveAttribute('aria-pressed', 'true');
  expect(
    screen.getByRole('button', { name: 'Remove exclusion provider: P1' })
  ).toBeInTheDocument();
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Select map' }));
  const selection = JSON.stringify({
    provider: { include: [], exclude: ['P1'], operator: 'or' },
  });
  for (const name of ['Export selected CSV', 'Export filtered CSV']) {
    expect(screen.getByRole('link', { name }).getAttribute('href')).toContain(
      encodeURIComponent(selection)
    );
  }
  fireEvent.click(
    screen.getByRole('button', { name: 'Remove exclusion provider: P1' })
  );
  expect(
    await screen.findByRole('button', { name: 'Exclude P1' })
  ).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(await screen.findByRole('button', { name: 'P1 (3)' }));
  fireEvent.click(await screen.findByRole('button', { name: 'P2 (2)' }));
  fireEvent.change(
    screen.getByRole('combobox', { name: 'Match included Provider' }),
    { target: { value: 'and' } }
  );
  expect(
    screen
      .getByRole('link', { name: 'Export filtered CSV' })
      .getAttribute('href')
  ).toContain(
    encodeURIComponent(
      JSON.stringify({
        provider: { include: ['P1', 'P2'], exclude: [], operator: 'and' },
      })
    )
  );
  fireEvent.click(await screen.findByRole('button', { name: 'Exclude P1' }));
  fireEvent.click(await screen.findByRole('button', { name: 'P1 (3)' }));
  expect(
    screen.queryByRole('button', { name: 'Remove exclusion provider: P1' })
  ).not.toBeInTheDocument();
});

it('shows ten values and offers searchable sorted pages with keyboard dismissal', async () => {
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/facets'))
      return ok([{ field: 'provider', label: 'Provider' }]);
    if (url.includes('/facets/provider')) {
      const params = new URL(url, 'http://localhost').searchParams;
      const offset = Number(params.get('offset'));
      return ok({
        items: Array.from({ length: offset ? 1 : 10 }, (_, index) => ({
          value: `P${offset + index}`,
          label: `Provider ${offset + index}`,
          count: 1000,
        })),
        more: !offset,
        total: 11,
      });
    }
    return ok({ items: [], total: 0, limit: 25 });
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  const more = await screen.findByRole('button', { name: 'More »' });
  expect(
    screen.getAllByRole('button', { name: /^Provider \d+ \(1000\)$/ })
  ).toHaveLength(10);
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  more.focus();
  fireEvent.click(more);
  const dialog = screen.getByRole('dialog', {
    name: 'More options for Provider',
  });
  const modal = within(dialog);
  await modal.findByText('Showing page 1 of 2 · 11 total values');
  fireEvent.change(modal.getByRole('combobox', { name: 'Sort by' }), {
    target: { value: 'alpha_desc' },
  });
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url]) => url.includes('sort=alpha_desc') && url.includes('limit=10')
      )
    ).toBe(true)
  );
  fireEvent.click(await modal.findByRole('button', { name: 'Next' }));
  await modal.findByText('Showing page 2 of 2 · 11 total values');
  expect(modal.getByLabelText('Facet values page')).toHaveFocus();
  expect(modal.getByRole('button', { name: 'Next' })).toBeDisabled();
  fireEvent.click(modal.getByRole('button', { name: 'Reset' }));
  await modal.findByText('Showing page 1 of 2 · 11 total values');
  const exclude = modal.getByRole('button', { name: 'Exclude Provider 0' });
  exclude.focus();
  fireEvent.click(exclude);
  expect(exclude).toHaveFocus();
  await modal.findByText('Showing page 1 of 2 · 11 total values');
  fireEvent(dialog, new Event('cancel', { bubbles: true }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(await screen.findByRole('button', { name: 'More »' })).toHaveFocus();
  expect(document.body.style.overflow).toBe('');
});

it('shows recent imports and preserves an inclusive date range in exports', async () => {
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/facets'))
      return ok([
        { field: 'imports', label: 'Imports' },
        { field: 'date_created', label: 'Date created' },
        { field: 'last_harvested', label: 'Last harvested' },
      ]);
    if (url.includes('/facets/imports'))
      return ok({
        items: [
          {
            value: 'batch-1',
            label: 'September harvest',
            count: 42,
            timestamp: '2026-09-22T12:00:00Z',
          },
        ],
        total: 1,
        more: false,
      });
    return ok({ items: [], total: 0, offset: 0, limit: 25 });
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'September harvest (42)' })
  );
  expect(
    fetch.mock.calls.some(
      ([url]) => url.includes('sort=recent') && url.includes('limit=20')
    )
  ).toBe(true);
  fireEvent.change(screen.getByLabelText('Find a filter'), {
    target: { value: 'harvest' },
  });
  expect(
    screen.getByText('Last harvested', { selector: 'summary' })
  ).toBeInTheDocument();
  expect(
    screen.queryByText('Imports', { selector: 'summary' })
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Find a filter'), {
    target: { value: '' },
  });
  fireEvent.click(screen.getByText('Date range filter'));
  fireEvent.change(screen.getByLabelText('From date'), {
    target: { value: '2026-09-01' },
  });
  fireEvent.change(screen.getByLabelText('Through date'), {
    target: { value: '2026-09-23' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Apply dates' }));
  await waitFor(() => {
    const href = screen
      .getByRole('link', { name: 'Export filtered CSV' })
      .getAttribute('href')!;
    const filters = JSON.parse(
      new URL(href, 'http://localhost').searchParams.get('filters')!
    );
    expect(filters).toEqual({
      imports: ['batch-1'],
      date_created: { from: '2026-09-01', to: '2026-09-23' },
    });
  });
  fireEvent.click(
    screen.getByRole('button', { name: /Date created: 2026-09-01/ })
  );
  expect(
    screen
      .getByRole('link', { name: 'Export filtered CSV' })
      .getAttribute('href')
  ).not.toContain('date_created');
});
