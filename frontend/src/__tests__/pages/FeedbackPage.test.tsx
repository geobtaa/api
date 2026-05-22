import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { vi } from 'vitest';
import { FeedbackPage } from '../../pages/FeedbackPage';

vi.mock('../../components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock('../../components/layout/Footer', () => ({
  Footer: () => <div data-testid="footer">Footer</div>,
}));

function renderFeedbackPage(element = <FeedbackPage />) {
  const router = createMemoryRouter([{ path: '/', element }], {
    initialEntries: ['/'],
  });

  return render(
    <HelmetProvider>
      <RouterProvider router={router} />
    </HelmetProvider>
  );
}

describe('FeedbackPage', () => {
  it('renders the migrated feedback form fields', () => {
    renderFeedbackPage();

    expect(
      screen.getByRole('heading', { name: /feedback/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/topic/i)).toBeRequired();
    expect(screen.getByLabelText(/description/i)).toBeRequired();
    expect(
      screen.getByRole('button', { name: /send feedback/i })
    ).toBeInTheDocument();
  });

  it('renders submission errors and preserves field values', () => {
    renderFeedbackPage(
      <FeedbackPage
        actionData={{
          status: 'error',
          message: 'Please review the highlighted fields.',
          fieldErrors: {
            email_address: 'Enter a valid email address.',
          },
          values: {
            name: 'Ada',
            email_address: 'not-an-email',
            topic: 'Question',
            description: 'Can someone follow up?',
          },
        }}
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Please review the highlighted fields.'
    );
    expect(screen.getByLabelText(/email address/i)).toHaveValue('not-an-email');
    expect(
      screen.getByText(/enter a valid email address/i)
    ).toBeInTheDocument();
  });

  it('renders a success message', () => {
    renderFeedbackPage(
      <FeedbackPage
        actionData={{
          status: 'success',
          message: 'Thank you for your feedback. Your message has been sent.',
        }}
      />
    );

    expect(screen.getByRole('status')).toHaveTextContent(
      'Thank you for your feedback.'
    );
  });
});
