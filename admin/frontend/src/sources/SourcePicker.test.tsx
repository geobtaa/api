import { fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { SourcePicker } from './SourcePicker';

function setup(canUse = true, canRead = true) {
  const fetch = vi.fn(async (url: string) => {
    const params = new URL(url, 'https://local').searchParams;
    return new Response(
      JSON.stringify({
        items:
          params.get('q') === 'missing'
            ? []
            : [{ source_id: 'B', title: 'Other Source' }],
        offset: Number(params.get('offset')),
        total: params.get('q') === 'missing' ? 0 : 12,
        limit: 10,
      })
    );
  });
  vi.stubGlobal('fetch', fetch);
  function Picker() {
    const [value, setValue] = useState<string | null>('A');
    return (
      <SourcePicker
        value={value}
        saved="A"
        canRead={canRead}
        canUse={canUse}
        change={setValue}
      />
    );
  }
  render(
    <RouterProvider
      router={createMemoryRouter([{ path: '/', element: <Picker /> }])}
    />
  );
  return fetch;
}
afterEach(() => vi.unstubAllGlobals());

it('chooses and undoes the Source for a new Set', async () => {
  setup();
  expect(screen.getByRole('link', { name: 'A' })).toHaveAttribute(
    'href',
    '/sources/A'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Choose Source' }));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Other Source — B' })
  );
  expect(screen.getByText('Selected Source: B (unsaved)')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Undo Source change' }));
  expect(
    screen.queryByText('Selected Source: B (unsaved)')
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Clear Source' }));
  expect(
    screen.getByText('Selected Source: Unmapped (unsaved)')
  ).toBeInTheDocument();
});

it('searches with the keyboard and paginates Source choices', async () => {
  const fetch = setup();
  fireEvent.click(screen.getByRole('button', { name: 'Choose Source' }));
  await screen.findByRole('button', { name: 'Other Source — B' });
  fireEvent.click(
    within(
      screen.getByRole('navigation', { name: 'Source choice pages' })
    ).getByRole('button', { name: 'Next' })
  );
  await screen.findByRole('button', { name: 'Other Source — B' });
  expect(fetch.mock.calls.some(([url]) => url.includes('offset=10'))).toBe(
    true
  );
  const search = screen.getByLabelText('Search Sources by title or ID');
  search.focus();
  fireEvent.change(search, { target: { value: 'missing' } });
  fireEvent.keyDown(search, { key: 'Enter' });
  await screen.findByText('No Sources found.');
  expect(search).toHaveFocus();
});

it('respects read and use permissions', () => {
  setup(false, false);
  expect(
    screen.queryByRole('button', { name: 'Choose Source' })
  ).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'A' })).not.toBeInTheDocument();
  expect(screen.getByText('A')).toBeInTheDocument();
});
