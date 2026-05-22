import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { vi } from 'vitest';
import { AboutPage } from '../../pages/AboutPage';

vi.mock('../../components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock('../../components/layout/Footer', () => ({
  Footer: () => <div data-testid="footer">Footer</div>,
}));

describe('AboutPage', () => {
  it('renders Geoportal-specific about content and local feedback link', () => {
    render(
      <HelmetProvider>
        <BrowserRouter>
          <AboutPage />
        </BrowserRouter>
      </HelmetProvider>
    );

    expect(
      screen.getByRole('heading', { name: /about the btaa geoportal/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/helps users find geospatial resources/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/most resources in the geoportal link to data stored/i)
    ).toBeInTheDocument();
  });
});
