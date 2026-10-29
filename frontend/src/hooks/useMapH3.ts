import { useEffect, useState } from 'react';
import { ApiError, fetchMapH3, type MapH3Response } from '../services/api';

const EMPTY_HEXES: MapH3Response['hexes'] = [];

export function useMapH3(
  query: string,
  bbox: string | null,
  resolution: number,
  queryString?: string,
  options?: { enabled?: boolean }
) {
  const scope = JSON.stringify([query, queryString]);
  const [entry, setEntry] = useState<{
    scope: string;
    data: MapH3Response;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enabled = options?.enabled !== false;
  // Retain the last viewport while refreshing, but never carry data across filters.
  const data = entry?.scope === scope ? entry.data : null;

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setLoading(true);
    setError(null);
    async function load(attempt = 0) {
      try {
        const response = await fetchMapH3(
          query,
          bbox ?? undefined,
          resolution,
          queryString,
          controller.signal
        );
        if (controller.signal.aborted) return;
        setEntry({ scope, data: response });
        setError(null);
        setLoading(false);
      } catch (error) {
        if (controller.signal.aborted) return;
        setError(
          error instanceof Error ? error.message : 'Failed to fetch hex data'
        );
        const retryable =
          !(error instanceof ApiError) ||
          error.status === 429 ||
          (error.status ?? 0) >= 500;
        if (retryable && attempt < 2) {
          const delay =
            error instanceof ApiError ? error.retryAfterMs : undefined;
          timer = setTimeout(
            () => void load(attempt + 1),
            delay ?? 1000 * 2 ** attempt
          );
        } else setLoading(false);
      }
    }
    // Coalesce consecutive zoom-button clicks and cancel superseded requests.
    timer = setTimeout(() => void load(), 150);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [enabled, query, bbox, resolution, queryString, scope]);

  const hexes = data?.hexes ?? EMPTY_HEXES;
  return {
    hexes,
    resolution: data?.resolution ?? resolution,
    globalCount: data?.globalCount ?? 0,
    hexCount: hexes.length,
    totalInView: hexes.reduce((sum, hex) => sum + hex.count, 0),
    loading: !enabled || loading,
    error,
  };
}
