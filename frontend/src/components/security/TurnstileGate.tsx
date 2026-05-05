import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile';
import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  clearTurnstileSessionToken,
  fetchTurnstileStatus,
  getTurnstileAction,
  getTurnstileSiteKey,
  isTurnstileConfigured,
  verifyTurnstileToken,
} from '../../services/turnstile';

type GateState = 'checking' | 'challenge' | 'verifying' | 'verified' | 'error';

export function TurnstileGate({ children }: { children: ReactNode }) {
  const configured = isTurnstileConfigured();
  const siteKey = getTurnstileSiteKey();
  const action = getTurnstileAction();
  const widgetRef = useRef<TurnstileInstance>();
  const [gateState, setGateState] = useState<GateState>(
    configured ? 'checking' : 'verified'
  );

  useEffect(() => {
    if (!configured) return;

    let cancelled = false;
    fetchTurnstileStatus()
      .then((verified) => {
        if (cancelled) return;
        setGateState(verified ? 'verified' : 'challenge');
      })
      .catch(() => {
        if (cancelled) return;
        clearTurnstileSessionToken();
        setGateState('challenge');
      });

    return () => {
      cancelled = true;
    };
  }, [configured]);

  const handleSuccess = useCallback(async (token: string) => {
    setGateState('verifying');
    try {
      await verifyTurnstileToken(token);
      setGateState('verified');
    } catch {
      setGateState('error');
      widgetRef.current?.reset();
    }
  }, []);

  const handleRecoverableWidgetIssue = useCallback(() => {
    setGateState('challenge');
  }, []);

  if (!configured || gateState === 'verified') {
    return <>{children}</>;
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto flex min-h-screen w-full max-w-xl flex-col items-center justify-center px-6 py-12 text-center">
        <div className="w-full rounded border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="text-xl font-semibold tracking-normal">
            Verifying browser session
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            This quick check helps keep automated traffic from overwhelming the
            Geoportal.
          </p>

          <div className="mt-6 flex min-h-[76px] items-center justify-center">
            {gateState === 'checking' ? (
              <p className="text-sm text-slate-600">Checking session...</p>
            ) : (
              <Turnstile
                ref={widgetRef}
                siteKey={siteKey}
                onSuccess={handleSuccess}
                onExpire={handleRecoverableWidgetIssue}
                onError={handleRecoverableWidgetIssue}
                onTimeout={handleRecoverableWidgetIssue}
                options={{
                  action,
                  appearance: 'interaction-only',
                  refreshExpired: 'auto',
                  refreshTimeout: 'auto',
                  size: 'flexible',
                  theme: 'auto',
                }}
              />
            )}
          </div>

          {gateState === 'verifying' && (
            <p className="mt-4 text-sm text-slate-600">Finishing check...</p>
          )}
          {gateState === 'error' && (
            <p className="mt-4 text-sm text-red-700">
              Verification did not complete. Please try again.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
