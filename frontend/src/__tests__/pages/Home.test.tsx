import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { HomePage } from '../../pages/HomePage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';

describe('Home Page', () => {
  const renderHome = () => {
    render(
      <BrowserRouter>
        <ApiProvider>
          <DebugProvider>
            <HomePage />
          </DebugProvider>
        </ApiProvider>
      </BrowserRouter>
    );
  };

  it('renders the search input', () => {
    renderHome();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it('shows suggestions when typing', async () => {
    renderHome();
    const searchInput = screen.getByPlaceholderText(/search/i);
    await userEvent.type(searchInput, 'minnesota');

    await waitFor(() => {
      // The suggestions dropdown should appear with the mocked suggestion
      expect(screen.getByText('Minnesota')).toBeInTheDocument();
    });
  });
});
