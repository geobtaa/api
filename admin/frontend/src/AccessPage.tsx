import { Link } from 'react-router';
import { appUrl, request } from './api';
import { PasswordForm, AccountForm } from './LocalAccounts';
import { ui } from './ui/styles';
import { useEffect, useState } from 'react';

interface SessionActor {
  actor_id: string;
  kind: 'user' | 'service_account' | 'system';
  display_name: string;
  email: string | null;
  permissions: string[];
  set_ids: string[] | null;
}

interface SessionResponse {
  authenticated: true;
  actor: SessionActor;
}

type SessionState =
  | { status: 'loading' }
  | { status: 'authenticated'; session: SessionResponse }
  | { status: 'unauthenticated' }
  | { status: 'error' };

export function AccessPage() {
  const [state, setState] = useState<SessionState>({ status: 'loading' });

  const [local, setLocal] = useState(false);
  const [generation, reload] = useState(0);
  const [logoutError, setLogoutError] = useState(false);
  useEffect(() => {
    let active = true;

    async function loadSession() {
      try {
        const response = await fetch(appUrl('/api/v1/admin/session'), {
          credentials: 'same-origin',
          headers: { Accept: 'application/json' },
        });

        if (active)
          setLocal(
            response.headers?.get('X-GEOMG-Auth-Mode') === 'local-password'
          );
        if (response.status === 401 || response.status === 403) {
          if (active) setState({ status: 'unauthenticated' });
          return;
        }

        if (!response.ok) throw new Error('Session request failed');
        const session = (await response.json()) as SessionResponse;
        if (active) setState({ status: 'authenticated', session });
      } catch {
        if (active) setState({ status: 'error' });
      }
    }

    void loadSession();
    return () => {
      active = false;
    };
  }, [generation]);

  return (
    <main id="main-content" className={ui.page}>
      <p className={ui.kicker}>Access</p>
      <h1>Administrative session</h1>
      <section
        className="mt-6 max-w-3xl rounded-lg border border-border bg-surface p-5 shadow-xs sm:p-6 [&>:last-child]:mb-0"
        aria-live="polite"
      >
        {state.status === 'loading' && <p>Checking access…</p>}

        {state.status === 'authenticated' && (
          <>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-active">
              Authenticated
            </p>
            <h2>{state.session.actor.display_name}</h2>
            {local ? (
              <div className="my-3">
                <p>
                  {state.session.actor.permissions.includes('identity:manage')
                    ? 'Administrator'
                    : 'Catalog editor'}
                </p>
                <Link className={ui.backLink} to="/resources">
                  Open catalog
                </Link>
              </div>
            ) : (
              <dl className={ui.definitionList}>
                <div>
                  <dt>Actor type</dt>
                  <dd>{state.session.actor.kind.replace('_', ' ')}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{state.session.actor.email ?? 'Not supplied'}</dd>
                </div>
                <div>
                  <dt>Permissions</dt>
                  <dd>
                    {state.session.actor.permissions.length > 0
                      ? state.session.actor.permissions.join(', ')
                      : 'No permissions assigned'}
                  </dd>
                </div>
              </dl>
            )}
            {local && (
              <button
                type="button"
                className={ui.secondary}
                onClick={async () => {
                  try {
                    await request('/api/v1/admin/session', {
                      method: 'DELETE',
                      headers: { 'X-GEOMG-Request': '1' },
                    });
                    setState({ status: 'unauthenticated' });
                    setLogoutError(false);
                  } catch {
                    setLogoutError(true);
                  }
                }}
              >
                Sign out
              </button>
            )}
            {logoutError && (
              <p role="alert">Sign-out could not be confirmed. Try again.</p>
            )}
            {local &&
              state.session.actor.set_ids === null &&
              state.session.actor.permissions.includes('identity:manage') && (
                <details className="mt-6">
                  <summary className="cursor-pointer">Tester accounts</summary>
                  <AccountForm />
                </details>
              )}
          </>
        )}

        {state.status === 'unauthenticated' && local && (
          <PasswordForm onSuccess={() => reload(generation + 1)} />
        )}
        {state.status === 'unauthenticated' && !local && (
          <>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-active">
              Authentication required
            </p>
            <h2>This administrative route is protected.</h2>
            <p>
              Local development requires the explicit development identity.
              Production remains closed until institutional sign-in is
              configured.
            </p>
          </>
        )}

        {state.status === 'error' && (
          <>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-active">
              Unavailable
            </p>
            <h2>Session status could not be loaded.</h2>
            <p>Check the API connection and try again.</p>
          </>
        )}
      </section>
    </main>
  );
}
