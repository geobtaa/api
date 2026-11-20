import { useState, type FormEvent } from 'react';
import { ApiError, request } from './api';
import { ActionButton, SelectControl, TextInput } from './ui/controls';
import { ui } from './ui/styles';

const base = '/api/v1/admin/identity/local';
function post(body: unknown, key?: string): RequestInit {
  return {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-GEOMG-Request': '1',
      ...(key ? { 'Idempotency-Key': key } : {}),
    },
    body: JSON.stringify(body),
  };
}

export function PasswordForm({ onSuccess }: { onSuccess: () => void }) {
  const [setup, setSetup] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError('');
    try {
      await request(
        base + '/sessions',
        post({
          email: data.get('email'),
          password: data.get('password'),
          ...(setup ? { setup_code: data.get('code') } : {}),
        })
      );
      form.reset();
      onSuccess();
    } catch (e) {
      setError(
        e instanceof ApiError && e.code === 'unauthenticated'
          ? 'Sign-in details are incorrect or expired.'
          : (e as Error).message
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="grid max-w-md gap-3" onSubmit={submit}>
      <h2>{setup ? 'Set your GEOMG password' : 'Sign in to GEOMG'}</h2>
      <label>
        Email
        <TextInput required name="email" type="email" autoComplete="username" />
      </label>
      {setup && (
        <label>
          Setup code
          <TextInput required name="code" autoComplete="one-time-code" />
        </label>
      )}
      <label>
        {setup ? 'New password (at least 15 characters)' : 'Password'}
        <TextInput
          key={String(setup)}
          name="password"
          required
          type="password"
          minLength={setup ? 15 : undefined}
          maxLength={256}
          autoComplete={setup ? 'new-password' : 'current-password'}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <ActionButton disabled={busy} className={ui.primary}>
        {setup ? 'Set password and sign in' : 'Sign in'}
      </ActionButton>
      <ActionButton
        type="button"
        disabled={busy}
        onClick={() => {
          setSetup(!setup);
          setError('');
        }}
      >
        {setup ? 'Use an existing password' : 'Use a setup or reset code'}
      </ActionButton>
      {setup && <p>Ask your GEOMG administrator for a setup code.</p>}
    </form>
  );
}

export function AccountForm() {
  const [reset, setReset] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(() => crypto.randomUUID());
  function changed() {
    setCode('');
    setError('');
    setKey(crypto.randomUUID());
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError('');
    setBusy(true);
    try {
      const result = await request<{ setup_code: string | null }>(
        base + (reset ? '/resets' : '/accounts'),
        post({ email: data.get('email') }, key)
      );
      setCode(
        result.setup_code ||
          'This code was already issued. Request a reset if it was lost.'
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      className="mt-6 grid max-w-md gap-3"
      onSubmit={submit}
      onChange={changed}
    >
      <label>
        Action
        <SelectControl
          value={reset ? 'reset' : 'create'}
          onChange={(e) => setReset(e.target.value === 'reset')}
        >
          <option value="create">Create a tester account</option>
          <option value="reset">Reset a tester password</option>
        </SelectControl>
      </label>
      <label>
        Tester email
        <TextInput required type="email" name="email" />
      </label>
      {reset && (
        <p>
          Issuing a reset code ends the tester’s active sessions and disables
          their current password.
        </p>
      )}
      <ActionButton disabled={busy}>
        {reset ? 'Issue reset code' : 'Create account'}
      </ActionButton>
      {error && <p role="alert">{error}</p>}
      {code && (
        <p role="status">
          Share privately with the tester. The code expires in 30 minutes.{' '}
          <code>{code}</code>
        </p>
      )}
    </form>
  );
}
