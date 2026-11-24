import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { SetWorkflowsPage } from './SetWorkflows';

afterEach(() => vi.unstubAllGlobals());

function setup(status = 'active', unavailable = false) {
  const fetch = vi.fn(async (url: string) => {
    let value: unknown;
    if (url.startsWith('/api/v1/admin/sets/')) {
      value = unavailable
        ? {
            detail: {
              code: 'not_found',
              message: 'Set not found or inaccessible',
            },
          }
        : { set_id: 'Maps_01', title: 'County maps', status };
      return new Response(JSON.stringify(value), {
        status: unavailable ? 404 : 200,
      });
    }
    if (url.includes('/contracts/')) {
      value = {
        can_create: true,
        process_types: [],
        configuration_schema: { properties: {} },
        configuration_schema_version: 1,
        maximum_processes: 100,
      };
    } else {
      value = { items: [], total: 0, limit: 20, offset: 0 };
    }
    return new Response(JSON.stringify(value));
  });
  vi.stubGlobal('fetch', fetch);
  const router = createMemoryRouter(
    [
      { path: '/sets/:setId/workflows', element: <SetWorkflowsPage /> },
      { path: '/sets/:setId', element: <h1>Set details</h1> },
    ],
    { initialEntries: ['/sets/Maps_01/workflows'] }
  );
  render(<RouterProvider router={router} />);
  return { fetch, router };
}

it('loads the managing Set and protects unsaved Workflow edits when navigating away', async () => {
  const { fetch, router } = setup();
  await screen.findByRole('heading', { name: 'Workflows for County maps' });
  fireEvent.click(screen.getByRole('button', { name: 'Show Workflows' }));
  const title = await screen.findByLabelText('New Workflow title');
  expect(fetch.mock.calls.map(([url]) => url)).toContain(
    '/api/v1/admin/workflows?set_id=Maps_01&offset=0&limit=20'
  );
  fireEvent.change(title, { target: { value: 'Quarterly review' } });
  const unload = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(unload);
  expect(unload.defaultPrevented).toBe(true);
  fireEvent.click(screen.getByRole('link', { name: 'Back to Set' }));
  await screen.findByRole('dialog', { name: 'Discard unsaved changes?' });
  fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
  expect(title).toHaveValue('Quarterly review');
  expect(router.state.location.pathname).toBe('/sets/Maps_01/workflows');
  fireEvent.click(screen.getByRole('link', { name: 'Back to Set' }));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Discard changes' })
  );
  await screen.findByRole('heading', { name: 'Set details' });
});

it('allows viewing a retired Set without offering Workflow creation', async () => {
  setup('retired');
  fireEvent.click(
    await screen.findByRole('button', { name: 'Show Workflows' })
  );
  await waitFor(() =>
    expect(screen.getByText('0 Workflows in this Set')).toBeInTheDocument()
  );
  expect(screen.queryByLabelText('New Workflow title')).not.toBeInTheDocument();
});

it('does not load Workflows for an inaccessible Set', async () => {
  const { fetch } = setup('active', true);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'This record is unavailable or outside your access.'
  );
  expect(
    screen.queryByRole('button', { name: 'Show Workflows' })
  ).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});
