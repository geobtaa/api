import { afterEach, describe, expect, it, vi } from 'vitest';
import { isTurnstileConfigured } from '../../services/turnstile';

describe('turnstile service configuration', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('bypasses the browser gate in dev and test builds by default', () => {
    vi.stubEnv('VITE_TURNSTILE_ENABLED', 'true');
    vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'site-key');

    expect(isTurnstileConfigured()).toBe(false);
  });

  it('allows explicit local Turnstile testing in dev and test builds', () => {
    vi.stubEnv('VITE_TURNSTILE_ENABLED', 'true');
    vi.stubEnv('VITE_TURNSTILE_ENABLE_LOCAL', 'true');
    vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'site-key');

    expect(isTurnstileConfigured()).toBe(true);
  });

  it('keeps Turnstile disabled when the enabled flag is false', () => {
    vi.stubEnv('VITE_TURNSTILE_ENABLED', 'false');
    vi.stubEnv('VITE_TURNSTILE_ENABLE_LOCAL', 'true');
    vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'site-key');

    expect(isTurnstileConfigured()).toBe(false);
  });
});

describe('Turnstile service failures', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.useRealTimers();
  });

  it('preserves safe backend codes and honors rate-limit cooldowns', async () => {
    const { verifyTurnstileToken, TurnstileVerificationError } =
      await import('../../services/turnstile');
    vi.stubEnv('VITE_API_BASE_URL', '/api/v1');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            data: {
              attributes: { error_codes: ['session-store-unavailable'] },
            },
          }),
          { status: 503 }
        )
      )
    );
    const error = await verifyTurnstileToken('token').catch((error) => error);
    expect(error).toBeInstanceOf(TurnstileVerificationError);
    expect(error.errorCodes).toEqual(['session-store-unavailable']);
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('{}', { status: 429, headers: { 'Retry-After': '45' } })
        )
    );
    await expect(verifyTurnstileToken('token')).rejects.toMatchObject({
      retryAfterSeconds: 45,
    });
  });

  it('does not mistake a failed status check for an unverified session', async () => {
    const { fetchTurnstileStatus } = await import('../../services/turnstile');
    vi.stubEnv('VITE_API_BASE_URL', '/api/v1');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('{}', { status: 503 }))
    );
    await expect(fetchTurnstileStatus()).rejects.toThrow(
      'temporarily unavailable'
    );
  });

  it('aborts a stalled verification instead of leaving the gate spinning', async () => {
    const { verifyTurnstileToken } = await import('../../services/turnstile');
    vi.useFakeTimers();
    vi.stubEnv('VITE_API_BASE_URL', '/api/v1');
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url, options) =>
          new Promise((_resolve, reject) => {
            options.signal.addEventListener('abort', () =>
              reject(new Error('aborted'))
            );
          })
      )
    );
    const result = verifyTurnstileToken('token').catch((error) => error);
    await vi.advanceTimersByTimeAsync(15_000);
    expect((await result).message).toContain('timed out');
  });
});
