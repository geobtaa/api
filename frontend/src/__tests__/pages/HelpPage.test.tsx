import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { vi } from 'vitest';
import { HelpPage } from '../../pages/HelpPage';

vi.mock('../../components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock('../../components/layout/Footer', () => ({
  Footer: () => <div data-testid="footer">Footer</div>,
}));

describe('HelpPage', () => {
  it('renders Geoportal help content and local feedback link', () => {
    render(
      <HelmetProvider>
        <BrowserRouter>
          <HelpPage />
        </BrowserRouter>
      </HelmetProvider>
    );

    expect(
      screen.getByRole('heading', { name: /help/i, level: 1 })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /search the geoportal/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/select the gear icon at the end of the search bar/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/map controls allow you to/i)).toBeInTheDocument();
    expect(
      screen.getByText(/bookmarks stay in your browser/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /contact us/i })).toHaveAttribute(
      'href',
      '/feedback'
    );
  });
});
