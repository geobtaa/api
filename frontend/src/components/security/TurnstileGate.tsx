import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile';
import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useTheme } from '../../hooks/useTheme';
import {
  clearTurnstileSessionToken,
  fetchTurnstileStatus,
  getTurnstileAction,
  getTurnstileSiteKey,
  isTurnstileConfigured,
  TURNSTILE_REQUIRED_EVENT,
  verifyTurnstileToken,
} from '../../services/turnstile';

type GateState = 'checking' | 'challenge' | 'verifying' | 'verified' | 'error';

export function TurnstileGate({
  children,
  devPreview = false,
}: {
  children: ReactNode;
  devPreview?: boolean;
}) {
  const configured = isTurnstileConfigured();
  const previewMode = devPreview && import.meta.env.DEV;
  const gateEnabled = configured || previewMode;
  const siteKey = getTurnstileSiteKey();
  const action = getTurnstileAction();
  const { theme } = useTheme();
  const institutionName = theme.institution.name || 'BTAA Geoportal';
  const logoUrl = theme.institution.logo_url || '/btaa-logo.png';
  const lockupText = theme.institution.logo_lockup?.right_text || 'Geoportal';
  const widgetRef = useRef<TurnstileInstance>();
  const [gateState, setGateState] = useState<GateState>(
    gateEnabled ? (previewMode ? 'challenge' : 'checking') : 'verified'
  );

  useEffect(() => {
    if (previewMode) {
      setGateState('challenge');
      return;
    }

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
  }, [configured, previewMode]);

  useEffect(() => {
    if (!gateEnabled || typeof window === 'undefined') return;

    const handleTurnstileRequired = () => {
      clearTurnstileSessionToken();
      setGateState('challenge');
    };

    window.addEventListener(TURNSTILE_REQUIRED_EVENT, handleTurnstileRequired);
    return () => {
      window.removeEventListener(
        TURNSTILE_REQUIRED_EVENT,
        handleTurnstileRequired
      );
    };
  }, [gateEnabled]);

  const handleSuccess = useCallback(async (token: string) => {
    setGateState('verifying');
    try {
      await verifyTurnstileToken(token);
      setGateState('verified');
    } catch {
      setGateState('error');
      widgetRef.current?.reset?.();
    }
  }, []);

  const handleRecoverableWidgetIssue = useCallback(() => {
    setGateState('challenge');
  }, []);

  const handlePreviewContinue = useCallback(() => {
    window.location.assign('/');
  }, []);

  if (!gateEnabled || gateState === 'verified') {
    return <>{children}</>;
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <header className="bg-brand text-white shadow-[0_2px_10px_rgba(0,0,0,0.12)]">
        <div className="mx-auto flex w-full max-w-6xl items-center px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <img
              src={logoUrl}
              alt={`${institutionName} Logo`}
              className="h-12 w-auto shrink-0 object-contain sm:h-14"
            />
            <span aria-hidden="true" className="h-10 w-px bg-white/70" />
            <span className="min-w-0 text-2xl font-semibold tracking-normal">
              {lockupText}
            </span>
          </div>
        </div>
      </header>

      <section className="mx-auto w-full max-w-3xl px-4 pb-16 pt-16 sm:px-6 sm:pt-20 lg:px-8">
        <div className="border border-slate-200 bg-white shadow-xl">
          <div className="border-t-[6px] border-t-brand px-6 py-7 sm:px-8 sm:py-8">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand">
              Browser verification
            </p>
            <h1 className="mt-3 text-3xl font-semibold leading-tight text-slate-950 sm:text-[2.5rem]">
              Before entering the BTAA Geoportal
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
              This quick check helps keep search, maps, and downloads in the
              BTAA Geoportal responsive for researchers browsing public
              geospatial collections.
            </p>
          </div>

          <div className="border-t border-slate-200 bg-slate-50 px-6 py-6 sm:px-8">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand">
              {institutionName}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">
              Continue to the BTAA Geoportal
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {previewMode
                ? 'This local preview uses a mock verification control.'
                : 'Complete the verification check to continue to the BTAA Geoportal.'}
            </p>

            <div className="mt-6 border border-slate-200 bg-white p-4">
              <div className="flex min-h-[92px] items-center justify-center">
                {gateState === 'checking' ? (
                  <div className="flex items-center gap-3 text-sm text-slate-600">
                    <span
                      aria-hidden="true"
                      className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand"
                    />
                    <span>Checking your session...</span>
                  </div>
                ) : previewMode ? (
                  <div className="w-full max-w-sm text-center">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Local preview control
                    </p>
                    <button
                      type="button"
                      onClick={handlePreviewContinue}
                      className="mt-3 inline-flex w-full items-center justify-center rounded-full border border-brand bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#002f49] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2"
                    >
                      Continue to the BTAA Geoportal
                    </button>
                  </div>
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
                      appearance: 'always',
                      refreshExpired: 'auto',
                      refreshTimeout: 'auto',
                      size: 'flexible',
                      theme: 'auto',
                    }}
                  />
                )}
              </div>
            </div>

            <div aria-live="polite" role="status" className="mt-4 min-h-6">
              {gateState === 'verifying' && (
                <p className="text-sm text-slate-600">
                  Finishing verification...
                </p>
              )}
              {gateState === 'error' && (
                <p className="border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  Verification did not complete. Please try again.
                </p>
              )}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
