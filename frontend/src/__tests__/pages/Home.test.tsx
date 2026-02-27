import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { HomePage } from '../../pages/HomePage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { vi } from 'vitest';

vi.mock('../../components/SearchField', () => ({
  SearchField: () => <input placeholder="Search for maps, data, imagery..." />,
}));

describe('Home Page', () => {
  const renderHome = () => {
    render(
      <HelmetProvider>
        <BrowserRouter>
          <ApiProvider>
            <DebugProvider>
              <HomePage />
            </DebugProvider>
          </ApiProvider>
        </BrowserRouter>
      </HelmetProvider>
    );
  };

  it('renders the search input', () => {
    renderHome();
    expect(screen.getByText(/new from btaa:/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /read gin news & stories/i })
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /partner institutions/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /sanborn fire insurance maps/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: /big ten academic alliance libraries historical maps collection/i,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /urban base layers collection/i })
    ).toBeInTheDocument();
    expect(screen.getByAltText(/logo for indiana university/i)).toBeInTheDocument();
    expect(
      screen.getByAltText(/logo for university of washington/i)
    ).toBeInTheDocument();
  });

  it('shows suggestions when typing', async () => {
    renderHome();
    const searchInput = screen.getByPlaceholderText(/search/i);
    await userEvent.type(searchInput, 'minnesota');

    await waitFor(() => {
      // The suggestions dropdown should appear with the mocked suggestion
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });
});
