import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchFacetValues } from '../services/api';
import { debugLog } from '../utils/logger';
import type {
  FacetValue,
  FacetValuesMeta,
  FacetValuesSort,
} from '../types/api';

export interface UseFacetModalOptions {
  facetId: string;
  isOpen: boolean;
  searchParams: URLSearchParams;
  perPage?: number;
  defaultSort?: FacetValuesSort;
}

const DEFAULT_PER_PAGE = 10;
const DEFAULT_SORT: FacetValuesSort = 'count_desc';

export function useFacetModal({
  facetId,
  isOpen,
  searchParams,
  perPage = DEFAULT_PER_PAGE,
  defaultSort = DEFAULT_SORT,
}: UseFacetModalOptions) {
  const [items, setItems] = useState<FacetValue[]>([]);
  const [meta, setMeta] = useState<FacetValuesMeta | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPageState] = useState(1);
  const [perPageState, setPerPageState] = useState(perPage);
  const [sort, setSortState] = useState<FacetValuesSort>(defaultSort);
  const [qFacet, setQFacetState] = useState('');

  const paramsSignature = useMemo(
    () => searchParams.toString(),
    [searchParams]
  );
  const lastParamsRef = useRef<string>('');

  useEffect(() => {
    if (!isOpen || !facetId) {
      // Reset when modal closes
      if (!isOpen) {
        lastParamsRef.current = '';
        setItems([]);
        setMeta(null);
        setHasLoaded(false);
        setPageState(1);
      }
      return;
    }
    setItems([]);
    setMeta(null);
    setHasLoaded(false);
    setPageState(1);
  }, [facetId, isOpen]);

  useEffect(() => {
    setPerPageState(perPage);
  }, [perPage]);

  const loadFacetValues = useCallback(
    async ({
      nextPage = page,
      nextPerPage = perPageState,
      nextSort = sort,
      nextQFacet = qFacet,
    }: {
      nextPage?: number;
      nextPerPage?: number;
      nextSort?: FacetValuesSort;
      nextQFacet?: string;
    } = {}) => {
      if (!isOpen || !facetId) return;

      setIsLoading(true);
      setError(null);

      try {
        debugLog('🔍 Loading facet values:', {
          facetId,
          page: nextPage,
          perPage: nextPerPage,
          sort: nextSort,
          qFacet: nextQFacet,
          searchParams: searchParams.toString(),
        });

        const response = await fetchFacetValues({
          facetName: facetId,
          searchParams: new URLSearchParams(searchParams),
          page: nextPage,
          perPage: nextPerPage,
          sort: nextSort,
          qFacet: nextQFacet || undefined,
        });

        debugLog('✅ Facet values response:', {
          dataLength: response.data?.length || 0,
          meta: response.meta,
          totalCount: response.meta?.totalCount || 0,
        });

        setItems(response.data || []);
        setMeta(response.meta);
        setPageState(nextPage);
        setPerPageState(nextPerPage);
        setSortState(nextSort);
        setQFacetState(nextQFacet);
        setHasLoaded(true);
        lastParamsRef.current = paramsSignature;
      } catch (err) {
        console.error('❌ Error loading facet values:', err);
        setError(
          err instanceof Error ? err.message : 'Failed to load facet values'
        );
      } finally {
        setIsLoading(false);
      }
    },
    [
      facetId,
      isOpen,
      page,
      perPageState,
      sort,
      qFacet,
      paramsSignature,
      searchParams,
    ]
  );

  const loadFacetValuesRef = useRef(loadFacetValues);

  useEffect(() => {
    loadFacetValuesRef.current = loadFacetValues;
  }, [loadFacetValues]);

  useEffect(() => {
    if (!isOpen || !facetId) return;

    const paramsChanged = lastParamsRef.current !== paramsSignature;

    // Always load when modal opens
    // If params changed or we haven't loaded yet, reset to page 1
    if (paramsChanged || !hasLoaded) {
      lastParamsRef.current = paramsSignature;
      loadFacetValuesRef.current({ nextPage: 1 });
    } else {
      // Params unchanged and already loaded, just refetch with current state
      loadFacetValuesRef.current();
    }
  }, [facetId, isOpen, paramsSignature, hasLoaded]);

  const setPage = useCallback(
    (value: number) => {
      const normalized = Math.max(1, value);
      if (normalized === page) return;
      loadFacetValuesRef.current({ nextPage: normalized });
    },
    [page]
  );

  const setPerPage = useCallback(
    (value: number) => {
      const normalized = Math.max(1, Math.min(100, value));
      if (normalized === perPageState) return;
      loadFacetValuesRef.current({ nextPerPage: normalized, nextPage: 1 });
    },
    [perPageState]
  );

  const setSort = useCallback(
    (value: FacetValuesSort) => {
      if (value === sort) return;
      loadFacetValuesRef.current({ nextSort: value, nextPage: 1 });
    },
    [sort]
  );

  const setFacetQuery = useCallback(
    (value: string) => {
      if (value === qFacet) return;
      loadFacetValuesRef.current({ nextQFacet: value, nextPage: 1 });
    },
    [qFacet]
  );

  const resetFacetQuery = useCallback(() => {
    if (!qFacet) return;
    loadFacetValuesRef.current({ nextQFacet: '', nextPage: 1 });
  }, [qFacet]);

  const refetch = useCallback(() => {
    loadFacetValuesRef.current();
  }, []);

  return {
    items,
    meta,
    isLoading,
    error,
    page,
    perPage: perPageState,
    sort,
    qFacet,
    hasLoaded,
    setPage,
    setPerPage,
    setSort,
    setFacetQuery,
    resetFacetQuery,
    refetch,
  };
}
