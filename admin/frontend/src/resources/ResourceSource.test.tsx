import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { ResourceEditor } from './ResourceEditor';
import contract from './editor.contract.fixture.json';

afterEach(() => vi.unstubAllGlobals());
it('shows the Source inherited from the managing Set without independent assignment controls', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(contract)))
  );
  const router = createMemoryRouter([
    {
      path: '/',
      element: (
        <ResourceEditor
          item={{
            id: 'map/1',
            source_id: 'parent',
            set_id: 'one-of-many',
            set_title: 'County maps',
            publication_state: 'draft',
            lock_version: 1,
            editable: true,
            metadata: {
              dct_title_s: 'Map',
              dct_source_sm: ['Descriptive source'],
            },
            distributions: [],
            source_record: {},
            import_warnings: [],
          }}
          onSaved={() => {}}
        />
      ),
    },
  ]);
  render(<RouterProvider router={router} />);
  expect(await screen.findByRole('link', { name: 'parent' })).toHaveAttribute(
    'href',
    '/sources/parent'
  );
  expect(screen.getByRole('link', { name: 'County maps' })).toHaveAttribute(
    'href',
    '/sets/one-of-many'
  );
  expect(screen.getByText(/Inherited from managing Set/)).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Choose Source' })
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Clear Source' })
  ).not.toBeInTheDocument();
});
