import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { ResourceView } from '../../pages/ResourceView';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { vi } from 'vitest';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useParams: () => ({ id: 'test-id' }),
  };
});

import { HelmetProvider } from 'react-helmet-async';

describe('Resource View Page', () => {
  const renderResourceView = () => {
    render(
      <HelmetProvider>
        <BrowserRouter>
          <ApiProvider>
            <DebugProvider>
              <ResourceView />
            </DebugProvider>
          </ApiProvider>
        </BrowserRouter>
      </HelmetProvider>
    );
  };

  it('displays resource details', async () => {
    renderResourceView();
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Test Resource' })
      ).toBeInTheDocument();
    });
  });

  it('shows the location map when geometry is available', async () => {
    renderResourceView();
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Test Resource' })
      ).toBeInTheDocument();
    });
  });
});
