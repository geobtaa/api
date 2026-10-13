import { render, screen, waitFor } from '@testing-library/react';
import {
  createMemoryRouter,
  RouterProvider,
  type ActionFunctionArgs,
} from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import AnalyticsLogin from '../../app/routes/analytics.login';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});
it('clears the email token and automatically verifies it once', async () => {
  const token = 'a'.repeat(43);
  window.history.replaceState(null, '', '/analytics/login#token=' + token);
  const action = vi.fn<
    (args: ActionFunctionArgs) => Promise<{ message: string; error: string }>
  >(async () => ({ message: 'Signed in', error: '' }));
  const router = createMemoryRouter(
    [{ path: '/analytics/login', Component: AnalyticsLogin, action }],
    { initialEntries: ['/analytics/login'] }
  );
  render(<RouterProvider router={router} />);
  await waitFor(() => expect(action).toHaveBeenCalledTimes(1));
  expect(window.location.hash).toBe('');
  expect(
    screen.queryByRole('button', { name: 'Continue to analytics' })
  ).toBeNull();
  const form = await action.mock.calls[0][0].request.formData();
  expect(form.get('token')).toBe(token);
  expect(form.get('intent')).toBe('verify');
});

it('shows Google sign-in instead of the email form when configured', async () => {
  const router = createMemoryRouter(
    [
      {
        path: '/analytics/login',
        Component: AnalyticsLogin,
        loader: () => ({ google: true, unavailable: false, error: '' }),
      },
    ],
    { initialEntries: ['/analytics/login'] }
  );
  render(<RouterProvider router={router} />);
  expect(
    await screen.findByRole('button', { name: 'Continue with Google' })
  ).toBeInTheDocument();
  expect(screen.queryByRole('textbox', { name: 'Email address' })).toBeNull();
  expect(
    screen.getByText(/we do not request access to your email or files/)
  ).toBeInTheDocument();
});
