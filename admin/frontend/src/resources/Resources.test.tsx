import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import {
  MemoryRouter,
  createMemoryRouter,
  RouterProvider,
  Routes,
  Route,
} from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import editorContract from './editor.contract.fixture.json';
import { ResourceDetail, ResourceList } from './ResourcePages';

const resource = {
  id: 'map/1',
  set_id: 'source-1',
  set_title: 'Demo collection',
  publication_state: 'draft',
  lock_version: 1,
  metadata: {
    id: 'map/1',
    dct_title_s: 'Historic map',
    gbl_resourceClass_sm: ['Maps'],
  },
};
const managingSet = {
  set_id: 'source-1',
  title: 'Demo collection',
  legacy_code: 'demo-collection',
};
const record = { id: 'map/1', dct_title_s: 'Historic map' };
function ok(data: unknown) {
  return { ok: true, json: async () => data };
}
afterEach(() => vi.unstubAllGlobals());

it('searches and pages through saved Resources', async () => {
  const fetch = vi.fn(async (url: string) =>
    ok(
      url.includes('offset=25')
        ? { items: [], total: 26, limit: 25 }
        : { items: [resource], total: 26, limit: 25, can_validate: true }
    )
  );
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  expect(
    await screen.findByRole('link', { name: 'Historic map' })
  ).toHaveAttribute('href', '/resources/~bWFwLzE');
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select map/1' }));
  expect(
    screen.getByRole('link', { name: 'Export selected CSV' })
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Validate selected drafts' })
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'Unassigned drafts' })
  ).not.toBeInTheDocument();
  fireEvent.click(
    within(
      screen.getByRole('navigation', { name: 'Resource pagination top' })
    ).getByRole('button', { name: 'Next' })
  );
  expect(await screen.findByText(/No Resources match/)).toBeInTheDocument();
  fireEvent.click(
    within(
      screen.getByRole('navigation', { name: 'Resource pagination bottom' })
    ).getByRole('button', { name: 'Previous' })
  );
  await screen.findByRole('link', { name: 'Historic map' });
  fireEvent.change(screen.getByLabelText('Search title or Resource ID'), {
    target: { value: 'Historic' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining('q=Historic'),
      expect.anything()
    )
  );
});
it('recovers from a Resource list dependency failure', async () => {
  let fail = true;
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/facets')) return ok([]);
    if (fail) {
      fail = false;
      throw new Error('offline');
    }
    return ok({ items: [], total: 0, offset: 0, limit: 25 });
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter>
      <ResourceList />
    </MemoryRouter>
  );
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(
    await screen.findByText('0 Resources · 0 selected on page')
  ).toBeInTheDocument();
});
it('opens standalone metadata and offers first assignment to authorized staff', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/relationships?'))
        return ok({ items: [], total: 0, offset: 0, limit: 25 });
      if (url.includes('/contracts/resources'))
        return ok({ ...editorContract, can_update: false });
      return ok({
        ...resource,
        set_id: null,
        set_title: null,
        source_id: null,
        can_associate: true,
        source_record: record,
        import_warnings: ['Incomplete source'],
      });
    })
  );
  render(
    <RouterProvider
      router={createMemoryRouter(
        [{ path: '/resources/:resourceId', element: <ResourceDetail /> }],
        { initialEntries: ['/resources/~bWFwLzE'] }
      )}
    />
  );
  expect(
    await screen.findByRole('heading', { name: 'Historic map' })
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'Change managing Set' })
  ).not.toBeInTheDocument();
  expect(screen.queryByText('Unassigned')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Assign to a Set' })).toHaveAttribute(
    'href',
    '/resources/~bWFwLzE/set'
  );
  expect(
    screen.queryByText(/Inherited from managing Set/)
  ).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/admin/resources/~bWFwLzE',
    expect.anything()
  );
  const relationshipsTab = await screen.findByRole('tab', {
    name: 'Relationships',
  });
  expect(
    screen.queryByRole('region', { name: 'Relationships' })
  ).not.toBeInTheDocument();
  fireEvent.click(relationshipsTab);
  const metadataPanel = screen.getByRole('tabpanel', {
    name: 'Relationships',
  });
  expect(
    await within(metadataPanel).findByText('No saved relationships.')
  ).toBeVisible();
  fireEvent.click(screen.getByText('Import evidence and warnings'));
  expect(screen.getByText('Incomplete source')).toBeVisible();
});
it('reports a missing or inaccessible Resource', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }));
  render(
    <MemoryRouter initialEntries={['/resources/missing']}>
      <Routes>
        <Route path="/resources/:resourceId" element={<ResourceDetail />} />
      </Routes>
    </MemoryRouter>
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Resource unavailable'
  );
});

it('retains Set scope through search, paging, detail links, and explicit clearing', async () => {
  const fetch = vi.fn(async (url: string) =>
    url.includes('/sets/')
      ? ok(managingSet)
      : ok({ items: [resource], total: 26, limit: 25 })
  );
  vi.stubGlobal('fetch', fetch);
  render(
    <MemoryRouter initialEntries={['/resources?set_id=source-1']}>
      <ResourceList />
    </MemoryRouter>
  );
  await screen.findByRole('link', { name: 'Historic map' });
  expect(
    screen.queryByRole('link', { name: 'Import JSON' })
  ).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Import CSV' })).toHaveAttribute(
    'href',
    '/resources/csv?set_id=source-1'
  );
  expect(screen.getByRole('link', { name: 'Historic map' })).toHaveAttribute(
    'href',
    '/resources/~bWFwLzE?set_id=source-1'
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('set_id=source-1'),
      expect.anything()
    )
  );
  fireEvent.change(screen.getByLabelText('Search title or Resource ID'), {
    target: { value: 'Historic' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await screen.findByRole('link', { name: 'Historic map' });
  fireEvent.click(
    within(
      screen.getByRole('navigation', { name: 'Resource pagination top' })
    ).getByRole('button', { name: 'Next' })
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining('q=Historic&offset=25&set_id=source-1'),
      expect.anything()
    )
  );
  expect(
    await screen.findByRole('link', { name: 'Historic map' })
  ).toHaveAttribute(
    'href',
    '/resources/~bWFwLzE?set_id=source-1&q=Historic&offset=25'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Clear Set filter' }));
  await waitFor(() =>
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/admin/resources?q=Historic&offset=0',
      expect.anything()
    )
  );
  expect(
    screen.queryByRole('button', { name: 'Clear Set filter' })
  ).not.toBeInTheDocument();
});
it('returns from detail to the same filtered Resource page', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        ok({ ...resource, source_record: record, import_warnings: [] })
      )
  );
  render(
    <MemoryRouter
      initialEntries={[
        '/resources/~bWFwLzE?set_id=source-1&q=Historic&offset=25',
      ]}
    >
      <Routes>
        <Route path="/resources/:resourceId" element={<ResourceDetail />} />
      </Routes>
    </MemoryRouter>
  );
  expect(screen.getByRole('link', { name: '← Resources' })).toHaveAttribute(
    'href',
    '/resources?set_id=source-1&q=Historic&offset=25'
  );
  await screen.findByRole('heading', { name: 'Historic map' });
});
it('keeps the filter visible if its Set label cannot load', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/sets/')) throw new Error('denied');
      return ok({ items: [], total: 0, limit: 25 });
    })
  );
  render(
    <MemoryRouter initialEntries={['/resources?set_id=source-1']}>
      <ResourceList />
    </MemoryRouter>
  );
  await screen.findByText('0 Resources · 0 selected on page');
  expect(screen.getByRole('link', { name: 'source-1' })).toBeInTheDocument();
});
