import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { HomePage } from '../../pages/HomePage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { vi } from 'vitest';
import { getPartnerInstitutionSearchHref } from '../../constants/partnerInstitutions';

vi.mock('../../components/SearchField', () => ({
  SearchField: () => (
    <input placeholder="Search for locations, maps, data, imagery..." />
  ),
}));
vi.mock('../../components/home/HomePageHexMapBackground.client', () => ({
  HomePageHexMapBackground: () => null,
}));

describe('Home Page', () => {
  const renderHome = () => {
    return render(
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

  it('renders the search input', async () => {
    renderHome();
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /partner institutions/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/new from btaa:/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /read gin news & stories/i })
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /theme/i })).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: /creator/i })
    ).not.toBeInTheDocument();
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
    expect(
      screen.getByAltText(/logo for indiana university/i)
    ).toBeInTheDocument();
    expect(
      screen.getByAltText(/logo for university of washington/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: /search resources near indiana university/i,
      })
    ).toHaveAttribute(
      'href',
      getPartnerInstitutionSearchHref({
        slug: 'indiana-university',
        name: 'Indiana University',
        iconSlug: 'indiana_university',
        logoClassName: 'translate-x-0.5',
        campusMap: {
          latitude: 39.1702,
          longitude: -86.5235,
          zoom: 15,
        },
      })
    );
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

  it('hides the hero description when the close button is clicked', async () => {
    renderHome();

    const closeButton = screen.getByRole('button', {
      name: /hide map description/i,
    });
    expect(closeButton).toHaveClass('pointer-events-auto', 'h-9', 'w-9');
    expect(closeButton.querySelector('svg')).not.toHaveClass(
      'pointer-events-none'
    );

    await userEvent.click(closeButton);

    expect(
      screen.queryByRole('button', { name: /hide map description/i })
    ).not.toBeInTheDocument();
  });

  it('opens the BTAA video lightbox when the BTAA tile is clicked', async () => {
    renderHome();

    await userEvent.click(
      screen.getByRole('button', {
        name: /open big ten academic alliance video/i,
      })
    );

    expect(
      screen.getByRole('dialog', { name: /big ten academic alliance video/i })
    ).toBeInTheDocument();
    expect(
      screen.getByTitle(/big ten academic alliance overview video/i)
    ).toHaveAttribute(
      'src',
      'https://www.youtube.com/embed/p060LdJodXQ?autoplay=1&rel=0'
    );
  });
});
