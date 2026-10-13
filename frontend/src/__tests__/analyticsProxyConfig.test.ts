import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('analytics action origins behind the deployment proxy', () => {
  it('allows only the configured public host', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://review.example.org/api/v1');
    vi.resetModules();
    const { default: config } = await import('../../react-router.config');
    expect(config.allowedActionOrigins).toEqual(['review.example.org']);
  });

  it('does not add origin exceptions for an unconfigured local build', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    vi.resetModules();
    const { default: config } = await import('../../react-router.config');
    expect(config.allowedActionOrigins).toEqual([]);
  });
});
