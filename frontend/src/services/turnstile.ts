const TURNSTILE_SESSION_STORAGE_KEY = 'btaa_turnstile_session';
const DEFAULT_TURNSTILE_ACTION = 'geoportal_gate';

type TurnstileStatusResponse = {
  data?: {
    attributes?: {
      enabled?: boolean;
      verified?: boolean;
    };
  };
};

type TurnstileVerifyResponse = {
  data?: {
    attributes?: {
      verified?: boolean;
      session_token?: string;
    };
  };
};

export function isTurnstileConfigured(): boolean {
  if (shouldBypassTurnstileInLocalDev()) return false;

  return (
    !isDisabledFlag(import.meta.env.VITE_TURNSTILE_ENABLED) &&
    Boolean(import.meta.env.VITE_TURNSTILE_SITE_KEY)
  );
}

export function getTurnstileSiteKey(): string {
  return import.meta.env.VITE_TURNSTILE_SITE_KEY || '';
}

export function getTurnstileAction(): string {
  return import.meta.env.VITE_TURNSTILE_ACTION || DEFAULT_TURNSTILE_ACTION;
}

export function getTurnstileSessionToken(): string | undefined {
  if (typeof window === 'undefined') return undefined;

  try {
    return (
      window.sessionStorage.getItem(TURNSTILE_SESSION_STORAGE_KEY) || undefined
    );
  } catch {
    return undefined;
  }
}

export function storeTurnstileSessionToken(sessionToken: string | undefined) {
  if (typeof window === 'undefined' || !sessionToken) return;

  try {
    window.sessionStorage.setItem(TURNSTILE_SESSION_STORAGE_KEY, sessionToken);
  } catch {
    // HttpOnly cookie verification still works for same-origin production traffic.
  }
}

export function clearTurnstileSessionToken() {
  if (typeof window === 'undefined') return;

  try {
    window.sessionStorage.removeItem(TURNSTILE_SESSION_STORAGE_KEY);
  } catch {
    // Ignore storage access failures.
  }
}

export async function fetchTurnstileStatus(): Promise<boolean> {
  const response = await fetch(getTurnstileEndpointUrl('status'), {
    headers: buildTurnstileHeaders(),
    credentials: getTurnstileCredentialsMode(),
    mode: 'cors',
  });

  if (!response.ok) return false;

  const payload = (await response.json()) as TurnstileStatusResponse;
  return Boolean(payload.data?.attributes?.verified);
}

export async function verifyTurnstileToken(token: string): Promise<void> {
  const response = await fetch(getTurnstileEndpointUrl('verify'), {
    method: 'POST',
    headers: {
      ...buildTurnstileHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ token }),
    credentials: getTurnstileCredentialsMode(),
    mode: 'cors',
  });

  if (!response.ok) {
    clearTurnstileSessionToken();
    throw new Error(`Turnstile verification failed with ${response.status}`);
  }

  const payload = (await response.json()) as TurnstileVerifyResponse;
  const attributes = payload.data?.attributes;
  if (!attributes?.verified) {
    clearTurnstileSessionToken();
    throw new Error('Turnstile verification was not accepted');
  }

  storeTurnstileSessionToken(attributes.session_token);
}

function buildTurnstileHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  const sessionToken = getTurnstileSessionToken();
  if (sessionToken) {
    headers['X-Turnstile-Session'] = sessionToken;
  }
  return headers;
}

function getTurnstileEndpointUrl(endpoint: 'status' | 'verify'): string {
  const apiBase = resolveApiBasePath().replace(/\/$/, '');
  const target = `${apiBase}/turnstile/${endpoint}`;
  if (target.startsWith('/')) {
    return new URL(target, window.location.origin).toString();
  }
  return target;
}

function resolveApiBasePath(): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (apiBaseUrl) return apiBaseUrl;

  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000/api/v1';
    }
  }

  return '/api/v1';
}

function getTurnstileCredentialsMode(): RequestCredentials {
  const target = new URL(getTurnstileEndpointUrl('status'));
  if (
    typeof window !== 'undefined' &&
    target.origin === window.location.origin
  ) {
    return 'same-origin';
  }
  return 'omit';
}

function isDisabledFlag(value: string | undefined): boolean {
  return ['0', 'false', 'no', 'off'].includes(
    String(value || '')
      .trim()
      .toLowerCase()
  );
}

function isEnabledFlag(value: string | undefined): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    String(value || '')
      .trim()
      .toLowerCase()
  );
}

function shouldBypassTurnstileInLocalDev(): boolean {
  const isDevOrTest = import.meta.env.DEV || import.meta.env.MODE === 'test';
  return (
    isDevOrTest &&
    !isEnabledFlag(import.meta.env.VITE_TURNSTILE_ENABLE_LOCAL)
  );
}
