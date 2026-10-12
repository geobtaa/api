import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { expect, it, vi } from 'vitest';
import { AnalyticsHeader } from '../components/analytics/AnalyticsHeader';

it('submits header sign-out through the router to the login action', async () => {
  const action = vi.fn(async ({ request }: { request: Request }) => {
    expect((await request.formData()).get('intent')).toBe('logout');
    return null;
  });
  const router = createMemoryRouter(
    [
      {
        path: '/analytics',
        element: <AnalyticsHeader activeReport="overview" />,
      },
      { path: '/analytics/login', action, element: <p>Sign in</p> },
    ],
    { initialEntries: ['/analytics'] }
  );
  render(<RouterProvider router={router} />);
  fireEvent.click(
    screen.getByRole('button', { name: 'Sign out of analytics' })
  );
  await waitFor(() => expect(action).toHaveBeenCalledTimes(1));
  expect(await screen.findByText('Sign in')).toBeInTheDocument();
});
