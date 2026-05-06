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
