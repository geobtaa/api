import { useEffect, useState } from 'react';
import { fetchMapH3, type MapH3Response } from '../services/api';

/** Stable empty array so useMapH3 doesn't return a new [] reference every render when data is null. */
const EMPTY_HEXES: MapH3Response['hexes'] = [];

export function useMapH3(
  query: string,
  bbox: string | null,
  resolution: number,
  queryString?: string,
  options?: { enabled?: boolean }
) {
  const [data, setData] = useState<MapH3Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enabled = options?.enabled !== false;

  useEffect(() => {
    if (!enabled) return;
    // bbox === null is valid: request global hexes (no bbox param)
    let mounted = true;
    setLoading(true);
    setError(null);
    fetchMapH3(query, bbox ?? undefined, resolution, queryString)
      .then((res) => {
        if (mounted) {
          setData(res);
          setError(null);
        }
      })
      .catch((e) => {
        if (mounted) {
          setData(null);
          setError(e instanceof Error ? e.message : 'Failed to fetch hex data');
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [enabled, query, bbox, resolution, queryString]);

  const hexCount = data?.hexes.length ?? 0;
  const totalInView = data?.hexes.reduce((s, h) => s + h.count, 0) ?? 0;
  return {
    hexes: data?.hexes ?? EMPTY_HEXES,
    globalCount: data?.globalCount ?? 0,
    hexCount,
    totalInView,
    loading: !enabled ? true : loading,
    error,
  };
}
