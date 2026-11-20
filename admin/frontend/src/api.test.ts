import { afterEach, expect, it, vi } from 'vitest';
import { ApiError, request } from './api';

afterEach(() => vi.unstubAllGlobals());
it('maps the documented validation envelope to recoverable field errors', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            detail: {
              code: 'validation_error',
              message: 'Check the supplied fields.',
              errors: [
                {
                  loc: ['body', 'distributions', 0, 'url'],
                  msg: 'Use an HTTP URL',
                  type: 'value_error',
                },
              ],
            },
          }),
          { status: 422 }
        )
    )
  );
  await expect(
    request('/api/v1/admin/resources/example')
  ).rejects.toMatchObject({
    code: 'validation',
    fields: [{ field: 'distributions.0.url', message: 'Use an HTTP URL' }],
  });
});
it('retains stable domain error codes without losing the recovery message', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            detail: {
              code: 'stale_version',
              message: 'Reload the current version.',
              errors: [],
            },
          }),
          { status: 409 }
        )
    )
  );
  await expect(request('/api/v1/admin/resources/example')).rejects.toEqual(
    new ApiError('Reload the current version.', 'stale_version')
  );
});
