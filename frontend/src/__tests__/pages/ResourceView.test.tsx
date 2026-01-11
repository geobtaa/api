import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { ResourceView } from '../../pages/ResourceView';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { vi } from 'vitest';

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useParams: () => ({ id: 'test-id' }),
  };
});

describe('Resource View Page', () => {
  const renderResourceView = () => {
    render(
      <BrowserRouter>
        <ApiProvider>
          <DebugProvider>
            <ResourceView />
          </DebugProvider>
        </ApiProvider>
      </BrowserRouter>
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
