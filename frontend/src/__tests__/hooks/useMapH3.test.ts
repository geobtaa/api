import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ApiError, fetchMapH3 } from '../../services/api';
import { useMapH3 } from '../../hooks/useMapH3';
vi.mock('../../services/api', async (original) => ({
  ...(await original<typeof import('../../services/api')>()),
  fetchMapH3: vi.fn(),
}));
const response = (resolution: number) => ({
  resolution,
  globalCount: 1,
  hexes: [{ h3: '822a17fffffffff', count: 12 }],
});
const advance = async (ms: number) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(fetchMapH3).mockReset();
});
afterEach(() => vi.useRealTimers());
it('retains successful hexes and their resolution through a 429, then updates on retry', async () => {
  vi.mocked(fetchMapH3)
    .mockResolvedValueOnce(response(2))
    .mockRejectedValueOnce(new ApiError('throttled', 429, undefined, 2000))
    .mockResolvedValueOnce(response(3));
  const { result, rerender } = renderHook(
    ({ zoom }) => useMapH3('', '-100,30,-70,50', zoom),
    { initialProps: { zoom: 2 } }
  );
  await advance(150);
  const old = result.current.hexes;
  rerender({ zoom: 3 });
  expect(result.current.hexes).toBe(old);
  await advance(150);
  expect(result.current.error).toBe('throttled');
  expect(result.current.hexes).toBe(old);
  expect(result.current.resolution).toBe(2);
  await advance(1999);
  expect(fetchMapH3).toHaveBeenCalledTimes(2);
  await advance(1);
  expect(result.current.resolution).toBe(3);
  expect(result.current.error).toBeNull();
});
it('coalesces rapid zoom changes, aborts obsolete requests, and ignores late responses', async () => {
  let resolveOld: (value: ReturnType<typeof response>) => void = () => {};
  vi.mocked(fetchMapH3)
    .mockResolvedValueOnce(response(2))
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        })
    )
    .mockResolvedValueOnce(response(5));
  const { result, rerender } = renderHook(
    ({ zoom }) => useMapH3('', null, zoom),
    { initialProps: { zoom: 2 } }
  );
  await advance(150);
  rerender({ zoom: 3 });
  await advance(150);
  const obsoleteSignal = vi.mocked(fetchMapH3).mock.calls[1][4]!;
  rerender({ zoom: 4 });
  await advance(50);
  rerender({ zoom: 5 });
  expect(obsoleteSignal.aborted).toBe(true);
  await advance(150);
  await act(async () => resolveOld(response(3)));
  expect(fetchMapH3).toHaveBeenCalledTimes(3);
  expect(result.current.resolution).toBe(5);
});
it('never retains stale filter results and bounds retry attempts for repeated failures', async () => {
  vi.mocked(fetchMapH3).mockResolvedValueOnce(response(2));
  const { result, rerender, unmount } = renderHook(
    ({ query }) => useMapH3(query, null, 2),
    { initialProps: { query: 'old' } }
  );
  await advance(150);
  vi.mocked(fetchMapH3).mockRejectedValue(new ApiError('unavailable', 503));
  rerender({ query: 'new' });
  expect(result.current.hexes).toEqual([]);
  await advance(150 + 1000 + 2000);
  expect(fetchMapH3).toHaveBeenCalledTimes(4);
  expect(result.current.loading).toBe(false);
  expect(result.current.error).toBe('unavailable');
  unmount();
  await advance(60000);
  expect(fetchMapH3).toHaveBeenCalledTimes(4);
});
it('cancels a scheduled retry on unmount', async () => {
  vi.mocked(fetchMapH3).mockRejectedValue(new ApiError('throttled', 429));
  const { unmount } = renderHook(() => useMapH3('', null, 2));
  await advance(150);
  unmount();
  await advance(5000);
  expect(fetchMapH3).toHaveBeenCalledTimes(1);
});
