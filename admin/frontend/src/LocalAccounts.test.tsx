import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AccountForm, PasswordForm } from './LocalAccounts';

afterEach(() => vi.unstubAllGlobals());

it('sets a password using the private setup code and opens the session', async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ authenticated: true }),
  });
  vi.stubGlobal('fetch', fetch);
  const done = vi.fn();
  render(<PasswordForm onSuccess={done} />);
  fireEvent.click(
    screen.getByRole('button', { name: 'Use a setup or reset code' })
  );
  fireEvent.change(screen.getByLabelText('Email'), {
    target: { value: 'tester@example.edu' },
  });
  fireEvent.change(screen.getByLabelText('Setup code'), {
    target: { value: 'private-test-code' },
  });
  fireEvent.change(screen.getByLabelText(/New password/), {
    target: { value: 'an example test password' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Set password and sign in' })
  );
  await waitFor(() => expect(done).toHaveBeenCalledOnce());
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    email: 'tester@example.edu',
    setup_code: 'private-test-code',
    password: 'an example test password',
  });
});

it('provisions scoped accounts and issues replacement codes', async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ setup_code: 'one-time-code' }),
  });
  vi.stubGlobal('fetch', fetch);
  render(
    <AccountForm permissions={['resources:read', 'admin.session:read']} />
  );
  fireEvent.change(screen.getByLabelText('Tester email'), {
    target: { value: 'tester@example.edu' },
  });
  fireEvent.change(screen.getByLabelText(/Managing Set IDs/), {
    target: { value: 'set-1, set-2' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
  expect(await screen.findByText('one-time-code')).toBeVisible();
  expect(JSON.parse(fetch.mock.calls[0][1].body).set_ids).toEqual([
    'set-1',
    'set-2',
  ]);
  fireEvent.change(screen.getByLabelText('Action'), {
    target: { value: 'reset' },
  });
  expect(screen.queryByText('one-time-code')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Issue reset code' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(fetch.mock.calls[1][0]).toBe('/api/v1/admin/identity/local/resets');
});
