import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResourceFixtures } from './ResourceFixtures';

const catalog = {
  source_commit: 'example',
  items: [
    {
      filename: 'map.json',
      purpose: 'Map',
      metadata: {
        id: 'map-1',
        dct_title_s: 'Historic map',
        gbl_resourceClass_sm: ['Maps'],
        schema_provider_s: 'Minnesota',
        gbl_suppressed_b: true,
        dct_description_sm: ['<script>alert(1)</script>'],
      },
    },
    {
      filename: 'data.json',
      purpose: 'Dataset',
      metadata: {
        id: 'data-2',
        dct_title_s: 'Roads',
        gbl_resourceClass_sm: ['Datasets'],
      },
    },
  ],
};
afterEach(() => vi.unstubAllGlobals());
it('browses and searches fixture metadata without rendering embedded HTML', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => catalog })
  );
  const { container } = render(<ResourceFixtures />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading');
  expect(await screen.findByText('Historic map')).toBeInTheDocument();
  expect(screen.getByText('Suppressed')).toBeInTheDocument();
  expect(container.querySelector('script')).toBeNull();
  fireEvent.click(screen.getAllByText('Inspect JSON')[0]);
  expect(screen.getByText('map.json')).toBeVisible();
  fireEvent.change(
    screen.getByLabelText('Search title, ID, provider, or class'),
    { target: { value: 'minnesota' } }
  );
  expect(screen.getByRole('status')).toHaveTextContent('1 of 2');
  expect(screen.queryByText('Roads')).not.toBeInTheDocument();
  fireEvent.change(
    screen.getByLabelText('Search title, ID, provider, or class'),
    { target: { value: 'nothing' } }
  );
  expect(
    screen.getByText('No fixtures match your search.')
  ).toBeInTheDocument();
});
it('allows recovery from an unavailable catalog', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ok: true, json: async () => catalog })
  );
  render(<ResourceFixtures />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('Historic map')).toBeInTheDocument();
});
it('ignores a response after leaving the page', async () => {
  let finish!: (value: unknown) => void;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      })
    )
  );
  const view = render(<ResourceFixtures />);
  view.unmount();
  finish({ ok: true, json: async () => catalog });
  await waitFor(() =>
    expect(screen.queryByText('Historic map')).not.toBeInTheDocument()
  );
});
