import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { SearchPage } from '../../pages/SearchPage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';

describe('Search Results Page', () => {
  const renderSearchResults = () => {
    render(
      <BrowserRouter>
        <ApiProvider>
          <DebugProvider>
            <SearchPage />
          </DebugProvider>
        </ApiProvider>
      </BrowserRouter>
    );
  };

  it('displays search results', async () => {
    renderSearchResults();
    await waitFor(() => {
      expect(screen.getByRole('main')).toBeInTheDocument();
    });
  });

  it('shows the map view', () => {
    renderSearchResults();
    // The map is always visible on large screens, check for map container
    expect(
      screen.getByRole('button', { name: /zoom in/i })
    ).toBeInTheDocument();
  });
});
