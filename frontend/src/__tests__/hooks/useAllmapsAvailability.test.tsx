import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useAllmapsAvailability } from '../../hooks/useAllmapsAvailability';
import fixture from '../integration/fixtures/allmaps/illinois.json';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const response = (body: unknown, ok = true) => ({ ok, json: async () => body });

describe('live Allmaps availability', () => {
  it('discovers annotations missing from harvested metadata on a fresh load', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(response({ type: 'AnnotationPage', items: [] }))
      .mockResolvedValueOnce(response(fixture.annotation));
    vi.stubGlobal('fetch', fetch);
    const first = renderHook(() =>
      useAllmapsAvailability('map', fixture.manifestUrl, null)
    );
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    first.unmount();
    const next = renderHook(() =>
      useAllmapsAvailability('map', fixture.manifestUrl, null)
    );
    await waitFor(() =>
      expect(next.result.current?.allmaps_annotated).toBe(true)
    );
    expect(fetch).toHaveBeenLastCalledWith(
      `https://annotations.allmaps.org/?url=${encodeURIComponent(fixture.manifestUrl)}`,
      expect.objectContaining({
        cache: 'no-store',
        credentials: 'omit',
        signal: expect.any(AbortSignal),
      })
    );
  });

  it('does not check resources without an eligible IIIF URL', () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    renderHook(() => useAllmapsAvailability('map', null, null));
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    response({}, false),
    response({}),
    response({ type: 'AnnotationPage', items: [] }),
  ])(
    'preserves harvested status when the check does not find valid maps',
    async (reply) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply));
      const stored = {
        allmaps_annotated: true,
        allmaps_manifest_uri: fixture.manifestUrl,
      };
      const { result } = renderHook(() =>
        useAllmapsAvailability('map', fixture.manifestUrl, stored)
      );
      await act(async () => {});
      expect(result.current).toEqual(stored);
    }
  );

  it('ignores a stale response after navigating to another resource', async () => {
    let resolve!: (value: unknown) => void;
    const fetch = vi.fn().mockReturnValue(
      new Promise((r) => {
        resolve = r;
      })
    );
    vi.stubGlobal('fetch', fetch);
    const { result, rerender } = renderHook(
      ({ id, url }) => useAllmapsAvailability(id, url, null),
      { initialProps: { id: 'old', url: fixture.manifestUrl as string | null } }
    );
    rerender({ id: 'new', url: null });
    await act(async () => {
      resolve(response(fixture.annotation));
    });
    expect(result.current).toBeNull();
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
  });

  it('aborts a stalled request after eight seconds', () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal('fetch', fetch);
    renderHook(() => useAllmapsAvailability('map', fixture.manifestUrl, null));
    act(() => vi.advanceTimersByTime(8000));
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
  });
});
