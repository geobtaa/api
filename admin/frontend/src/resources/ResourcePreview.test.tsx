import { render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ResourcePreview } from './ResourcePreview';
vi.mock('ogm-viewer', () => ({}));
it('always shows the preview and refreshes saved versions', async () => {
  const { container, rerender } = render(
    <ResourcePreview id="map/a:b" version={1} />
  );
  await waitFor(() =>
    expect(container.querySelector('ogm-viewer')).toHaveAttribute(
      'record-url',
      '/api/v1/admin/resources/~bWFwL2E6Yg/metadata?version=1'
    )
  );
  rerender(<ResourcePreview id="map/a:b" version={2} />);
  await waitFor(() =>
    expect(container.querySelector('ogm-viewer')).toHaveAttribute(
      'record-url',
      '/api/v1/admin/resources/~bWFwL2E6Yg/metadata?version=2'
    )
  );
  expect(screen.getByRole('heading', { name: 'Preview' })).toHaveClass(
    'sr-only'
  );
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
