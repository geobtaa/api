import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { expect, it } from 'vitest';
import AnalyticsLogin from '../../app/routes/analytics.login';

it('offers password sign-in without email or Google', () => {
  const router = createMemoryRouter(
    [{ path: '/analytics/login', Component: AnalyticsLogin }],
    { initialEntries: ['/analytics/login'] }
  );
  render(<RouterProvider router={router} />);
  expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText('Password')).toHaveAttribute(
    'autoComplete',
    'current-password'
  );
  expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  expect(screen.queryByText(/Google/)).toBeNull();
  expect(screen.queryByLabelText('Email address')).toBeNull();
  expect(
    screen.getByText(/Your access lasts for 24 hours/)
  ).toBeInTheDocument();
});
