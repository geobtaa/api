import {
  JsonApiResponse,
  GeoDocumentDetails,
  FacetValuesResponse,
  FacetValuesSort,
  GazetteerResponse,
  HomeBlogPostsResponse,
} from '../types/api';
import { AdvancedClause, FacetFilter } from '../types/search';
import { getActiveThemeConfig } from '../config/institution';
import { SEARCH_RESULTS_PER_PAGE } from '../constants/search';
import { debugLog, isDebugLoggingEnabled } from '../utils/logger';
import { getTurnstileSessionToken } from './turnstile';

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Builds headers for API requests.
 * Authentication (API key) is handled by the NGINX BFF proxy server-side,
 * so no authentication headers are needed in the client.
 */
const VISIT_TOKEN_STORAGE_KEY = 'btaa_visit_token';

function generateVisitToken(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID();
  }

  return `visit-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function getVisitToken(): string | undefined {
  if (typeof window === 'undefined') return undefined;

  try {
    const existing = window.sessionStorage.getItem(VISIT_TOKEN_STORAGE_KEY);
    if (existing) return existing;

    const nextToken = generateVisitToken();
    window.sessionStorage.setItem(VISIT_TOKEN_STORAGE_KEY, nextToken);
    return nextToken;
  } catch {
    return undefined;
  }
}

function buildApiHeaders(urlObj: URL): HeadersInit {
  const headers: Record<string, string> = {
    Accept: 'application/vnd.api+json, application/json',
  };

  const appVersion = import.meta.env.VITE_APP_VERSION || 'dev';

  // Only add custom analytics headers when they cannot trigger browser preflights:
  // server-side fetches or same-origin browser requests.
  if (typeof window === 'undefined') {
    headers['X-BTAA-Client-Name'] = 'geoportal-ssr';
    headers['X-BTAA-Client-Channel'] = 'ssr';
    headers['X-BTAA-Client-Version'] = appVersion;
    return headers;
  }

  if (urlObj.origin === window.location.origin) {
    headers['X-BTAA-Client-Name'] = 'geoportal-web';
    headers['X-BTAA-Client-Channel'] = 'browser';
    headers['X-BTAA-Client-Version'] = appVersion;

    const visitToken = getVisitToken();
    if (visitToken) {
      headers['X-Visit-Token'] = visitToken;
    }
  }

  const turnstileSessionToken = getTurnstileSessionToken();
  if (turnstileSessionToken) {
    headers['X-Turnstile-Session'] = turnstileSessionToken;
  }

  // Note: Content-Type is intentionally omitted for cross-origin requests to
  // avoid CORS preflight latency. When Turnstile is enabled, its session header
  // is allowed to preflight because protected API requests need to carry it.
  return headers;
}

const defaultFetchOptions: FetchOptions = {
  useJsonp: false, // Disable JSONP for modern JSON:API endpoints
};

// Add a request cache at the top of the file
const requestCache: Record<string, Promise<unknown> | undefined> = {};
// De-dupe in-flight regular fetches (helps avoid double-fetch in React StrictMode/dev).
const inFlightFetches = new Map<string, Promise<unknown>>();

// Helper function to ensure HTTPS URL
function ensureHttps(url: string): string {
  // Check if the environment variable for enforcing HTTPS is set to true
  const enforceHttps = import.meta.env.VITE_ENFORCE_HTTPS === 'true';
  if (enforceHttps) {
    return url.replace(/^http:/, 'https:');
  }
  return url;
}

function applyDefaultQueryParams(url: URL, defaults: string[] | undefined) {
  if (!defaults || defaults.length === 0) return;
  defaults.forEach((param) => {
    if (!param) return;
    const parsed = new URLSearchParams(param);
    parsed.forEach((value, key) => {
      const existing = url.searchParams.getAll(key);
      if (existing.includes(value)) return;
      url.searchParams.append(key, value);
    });
  });
}

function appendForwardedSearchFilters(
  target: URLSearchParams,
  source: URLSearchParams
) {
  Array.from(source.keys())
    .filter(
      (key) =>
        key.startsWith('include_filters[') ||
        key.startsWith('exclude_filters[') ||
        key.startsWith('fq[')
    )
    .forEach((key) => {
      source.getAll(key).forEach((value) => {
        target.append(key, value);
      });
    });
}

function getSearchResultsBasePath(): string {
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/search/results`;
  }

  return `${getApiBasePath()}/search`;
}

function toPublicSearchApiUrl(url: URL): string {
  if (url.pathname === '/search/results') {
    const publicUrl = new URL(url.toString());
    publicUrl.pathname = '/api/v1/search';
    return publicUrl.toString();
  }

  return url.toString();
}

/**
 * Gets the API base URL path for the NGINX BFF proxy.
 * The BFF proxy handles API key authentication server-side.
 * VITE_API_BASE_URL can override where the browser makes API requests.
 */
export function getApiBasePath(): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

  // If not set, provide a default (should be set via environment variable)
  if (!apiBaseUrl) {
    // Default fallback:
    // - Local dev: React app runs on :3000, API on :8000.
    // - Deployed: prefer same-origin /api/v1 (e.g., behind a reverse proxy).
    if (typeof window !== 'undefined') {
      const host = window.location.hostname;
      if (host === 'localhost' || host === '127.0.0.1') {
        return 'http://localhost:8000/api/v1';
      }
    }

    // If this ever gets called during SSR, avoid using localhost (it would point
    // at the frontend container). Same-origin /api/v1 is the safest default.
    return '/api/v1';
  }

  // Return the API base URL as-is (absolute URL to BFF proxy)
  return apiBaseUrl;
}

// Helper function to create a URL with common parameters
function createApiUrl(baseUrl: string): URL {
  // If baseUrl is a relative path, use current origin; otherwise use as-is
  const url = baseUrl.startsWith('/')
    ? new URL(baseUrl, window.location.origin)
    : new URL(ensureHttps(baseUrl));
  url.searchParams.set('format', 'json');

  // Apply always-on query params from the active theme config (theme.yaml).
  const theme = getActiveThemeConfig();
  applyDefaultQueryParams(url, theme?.api?.default_query_params);
  return url;
}

// Update the jsonp function to use the cache
function jsonp<T>(url: string, callbackName: string = 'rui'): Promise<T> {
  debugLog('Starting JSONP request:', url);

  // Check if this URL is already being requested
  const cacheKey = url;
  const cached = requestCache[cacheKey] as Promise<T> | undefined;
  if (cached) {
    debugLog('Using cached JSONP request for:', url);
    return cached;
  }

  // Create a new promise for this request
  const requestPromise = new Promise<T>((resolve, reject) => {
    const uniqueCallback = `${callbackName}_${Date.now()}`;
    debugLog('Using callback name:', uniqueCallback);
    let script: HTMLScriptElement | null = document.createElement('script');
    // Set timeout to prevent hanging requests
    const timeoutId = window.setTimeout(() => {
      console.error('JSONP request timed out:', url);
      cleanup();
      reject(new Error('JSONP request timed out'));
      // Remove from cache on timeout
      delete requestCache[cacheKey];
    }, 30000); // 30 second timeout

    // Cleanup function to remove script and callback
    const cleanup = () => {
      debugLog('Cleaning up JSONP request:', uniqueCallback);
      if (script && script.parentNode) {
        script.parentNode.removeChild(script);
      }
      delete (window as unknown as Record<string, unknown>)[uniqueCallback];
      window.clearTimeout(timeoutId);
      script = null;
    };

    // Add the callback to window
    (window as unknown as Record<string, unknown>)[uniqueCallback] = (
      data: T | { detail: string; path: string; method: string }
    ) => {
      debugLog('JSONP callback received data:', data);
      cleanup();

      // Check if response is an error
      if (typeof data === 'object' && data !== null && 'detail' in data) {
        console.error('JSONP error response:', data);
        reject(new ApiError(`API Error: ${data.detail}`));
        // Remove from cache on error
        delete requestCache[cacheKey];
        return;
      }

      resolve(data as T);
      // Keep successful responses in cache for 5 seconds
      setTimeout(() => {
        delete requestCache[cacheKey];
      }, 5000);
    };

    // Create script element with all properties set before appending to DOM
    const urlWithCallback = new URL(ensureHttps(url));
    urlWithCallback.searchParams.set('callback', uniqueCallback);
    if (!urlWithCallback.searchParams.has('format')) {
      urlWithCallback.searchParams.set('format', 'json');
    }

    debugLog('Final JSONP URL:', urlWithCallback.toString());

    if (script) {
      script.src = urlWithCallback.toString();
      script.onerror = (error) => {
        console.error('JSONP script error:', error);
        cleanup();
        reject(new Error('JSONP request failed'));
        // Remove from cache on error
        delete requestCache[cacheKey];
      };
      script.crossOrigin = 'anonymous';

      // Only append the script to the document once
      document.head.appendChild(script);
      debugLog('JSONP script added to document');
    }
  });

  // Store the promise in the cache
  requestCache[cacheKey] = requestPromise;
  return requestPromise;
}

interface FetchOptions {
  useJsonp?: boolean;
}

async function unifiedFetch<T>(
  url: string,
  options: FetchOptions = defaultFetchOptions
): Promise<T> {
  debugLog('unifiedFetch called with options:', {
    url,
    useJsonp: options.useJsonp,
    envValue: import.meta.env.VITE_USE_JSONP,
  });

  // Create URL object - all URLs should be absolute (pointing to BFF proxy)
  const urlObj = new URL(ensureHttps(url));

  // Ensure format parameter is set
  if (!urlObj.searchParams.has('format')) {
    urlObj.searchParams.set('format', 'json');
  }

  // For modern JSON:API endpoints, ensure proper Accept header
  if (url.includes('/resources/')) {
    // Remove any legacy parameters that might interfere with JSON:API
    urlObj.searchParams.delete('response_format');
    urlObj.searchParams.delete('datetime_format');
  }

  // Use absolute URL (all requests go directly to BFF proxy)
  const fetchUrl = urlObj.toString();
  const isSameOriginBrowserRequest =
    typeof window !== 'undefined' && urlObj.origin === window.location.origin;

  if (options.useJsonp) {
    debugLog('Using JSONP for request:', fetchUrl);
    return jsonp<T>(fetchUrl);
  }

  debugLog('Using regular fetch:', fetchUrl);

  try {
    // De-dupe concurrent GETs to the same URL (e.g., StrictMode double-invoked effects).
    const existing = inFlightFetches.get(fetchUrl) as Promise<T> | undefined;
    if (existing) return existing;

    const requestPromise: Promise<T> = (async () => {
      const response = await fetch(fetchUrl, {
        headers: buildApiHeaders(urlObj),
        mode: 'cors',
        credentials: isSameOriginBrowserRequest ? 'same-origin' : 'omit',
        redirect: 'follow',
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('API Error response:', errorText);
        try {
          const errorJson = JSON.parse(errorText);
          throw new ApiError(
            errorJson.detail || 'API request failed',
            response.status
          );
        } catch (e) {
          console.error('Error parsing API error response:', e);
          throw new ApiError(
            `HTTP error ${response.status}: ${errorText}`,
            response.status
          );
        }
      }

      const jsonData = await response.json();

      // Ensure thumbnail_url is preserved and enumerable in meta.ui objects
      // React Router serialization might remove non-enumerable properties
      if (jsonData && typeof jsonData === 'object' && 'data' in jsonData) {
        const apiResponse = jsonData as {
          data?: Array<{ meta?: { ui?: Record<string, unknown> } }>;
        };
        if (Array.isArray(apiResponse.data)) {
          apiResponse.data = apiResponse.data.map((item) => {
            if (item?.meta?.ui && typeof item.meta.ui === 'object') {
              // Check if thumbnail_url exists but might be non-enumerable
              const hasThumbnail = 'thumbnail_url' in item.meta.ui;
              const thumbnailValue = item.meta.ui.thumbnail_url as
                | string
                | undefined;

              // If thumbnail_url exists (even if undefined), ensure it's enumerable
              if (hasThumbnail || thumbnailValue) {
                // Re-set the property to ensure it's enumerable
                const value = thumbnailValue || item.meta.ui.thumbnail_url;
                if (value) {
                  Object.defineProperty(item.meta.ui, 'thumbnail_url', {
                    value: value,
                    enumerable: true,
                    writable: true,
                    configurable: true,
                  });
                }
              }
            }
            return item;
          });
        }
      }

      return jsonData;
    })();

    inFlightFetches.set(fetchUrl, requestPromise);
    try {
      return await requestPromise;
    } finally {
      inFlightFetches.delete(fetchUrl);
    }
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
}

export async function fetchSearchResults(
  query: string,
  page: number = 1,
  perPage: number = SEARCH_RESULTS_PER_PAGE,
  facets: FacetFilter[] = [],
  onApiCall?: (url: string) => void,
  sort?: string,
  excludeFacets: FacetFilter[] = [],
  advancedQuery: AdvancedClause[] = [],
  options: FetchOptions = defaultFetchOptions,
  sourceSearchParams?: URLSearchParams
): Promise<JsonApiResponse> {
  const startTime = performance.now();
  const resultPerPage = SEARCH_RESULTS_PER_PAGE;
  debugLog('🌐 fetchSearchResults called with:', {
    query,
    page,
    perPage: resultPerPage,
    requestedPerPage: perPage,
    facets: facets.length,
    sort,
    advancedClauses: advancedQuery.length,
  });

  const baseUrl = getSearchResultsBasePath();
  const url = createApiUrl(baseUrl);
  const effectiveQuery = sourceSearchParams?.get('q') ?? query;
  const effectiveSort = sort ?? sourceSearchParams?.get('sort') ?? undefined;
  const effectiveSearchField =
    sourceSearchParams?.get('search_field') || 'all_fields';

  url.searchParams.set('search_field', effectiveSearchField);
  url.searchParams.set('q', effectiveQuery);
  url.searchParams.set('page', page.toString());
  url.searchParams.set('per_page', resultPerPage.toString());

  if (sourceSearchParams) {
    appendForwardedSearchFilters(url.searchParams, sourceSearchParams);

    const rawAdvancedQuery = sourceSearchParams.get('adv_q');
    if (rawAdvancedQuery) {
      url.searchParams.set('adv_q', rawAdvancedQuery);
    }

    const cacheBust = sourceSearchParams.get('k6cb');
    if (cacheBust) {
      url.searchParams.set('k6cb', cacheBust);
    }
  } else if (typeof window !== 'undefined') {
    // Read geo filters from current URL if they exist
    // Only apply them if all required geo filter parameters are present
    // This ensures we don't apply partial or stale geo filters
    const currentUrl = new URL(window.location.href);
    const geoType = currentUrl.searchParams.get('include_filters[geo][type]');

    // Only apply geo filters if type is 'bbox' and all required params are present
    if (geoType === 'bbox') {
      const geoParams = [
        'include_filters[geo][type]',
        'include_filters[geo][field]',
        'include_filters[geo][top_left][lat]',
        'include_filters[geo][top_left][lon]',
        'include_filters[geo][bottom_right][lat]',
        'include_filters[geo][bottom_right][lon]',
      ];

      // Check if all required geo params are present
      const allGeoParamsPresent = geoParams.every(
        (key) => currentUrl.searchParams.get(key) !== null
      );

      // Only apply geo filters if all params are present
      if (allGeoParamsPresent) {
        geoParams.forEach((key) => {
          const value = currentUrl.searchParams.get(key);
          if (value) {
            url.searchParams.set(key, value);
          }
        });

        const relation = currentUrl.searchParams.get(
          'include_filters[geo][relation]'
        );
        if (relation) {
          url.searchParams.set('include_filters[geo][relation]', relation);
        }
      }
    }
  }

  if (effectiveSort && effectiveSort !== 'relevance') {
    url.searchParams.set('sort', effectiveSort);
  }

  // Normalize legacy *_agg facet IDs to field-named IDs for the API
  const FACET_ID_MAP: Record<string, string> = {
    spatial_agg: 'dct_spatial_sm',
    resource_class_agg: 'gbl_resourceClass_sm',
    resource_type_agg: 'gbl_resourceType_sm',
    provider_agg: 'schema_provider_s',
    creator_agg: 'dct_creator_sm',
    publisher_agg: 'dct_publisher_sm',
    access_rights_agg: 'dct_accessRights_s',
    access_agg: 'dct_accessRights_s',
    index_year_agg: 'gbl_indexyear_im',
    language_agg: 'b1g_language_sm',
    subject_agg: 'dct_subject_sm',
    institution_agg: 'schema_provider_s',
    format_agg: 'dct_format_s',
    georeferenced_agg: 'gbl_georeferenced_b',
    id_agg: 'id',
  };

  if (!sourceSearchParams) {
    facets.forEach(({ field, value }) => {
      const normalized = FACET_ID_MAP[field] || field;
      url.searchParams.append(`include_filters[${normalized}][]`, value);
    });

    // Apply exclude filters
    excludeFacets.forEach(({ field, value }) => {
      const normalized = FACET_ID_MAP[field] || field;
      url.searchParams.append(`exclude_filters[${normalized}][]`, value);
    });

    if (advancedQuery.length > 0) {
      const serialized = advancedQuery.map(({ op, field, q }) => ({
        op,
        f: FACET_ID_MAP[field] || field,
        q,
      }));
      url.searchParams.set('adv_q', JSON.stringify(serialized));
    }
  }

  const displayApiUrl = toPublicSearchApiUrl(url);

  debugLog('🔗 API URL:', displayApiUrl);

  if (onApiCall) {
    onApiCall(displayApiUrl);
  }

  try {
    const apiStartTime = performance.now();
    debugLog('📡 Making API request...');

    const response = await unifiedFetch<JsonApiResponse>(
      url.toString(),
      options
    );

    const apiEndTime = performance.now();
    const totalTime = performance.now() - startTime;

    debugLog(
      `⚡ API response received in ${(apiEndTime - apiStartTime).toFixed(2)}ms`
    );
    debugLog(`⏱️ Total fetchSearchResults time: ${totalTime.toFixed(2)}ms`);
    debugLog(`📦 Response data: ${response?.data?.length || 0} items`);

    // Debug: Check if thumbnail_url is present in the raw API response
    if (isDebugLoggingEnabled() && response?.data?.[0]) {
      const firstResult = response.data[0];
      debugLog('🔍 fetchSearchResults: First result meta structure:', {
        hasMeta: !!firstResult.meta,
        hasMetaUi: !!firstResult.meta?.ui,
        thumbnailUrl: firstResult.meta?.ui?.thumbnail_url,
        metaUiKeys: firstResult.meta?.ui
          ? Object.keys(firstResult.meta.ui)
          : [],
        metaUiStringified: firstResult.meta?.ui
          ? JSON.stringify(firstResult.meta.ui)
          : 'no ui',
        fullMetaStringified: firstResult.meta
          ? JSON.stringify(firstResult.meta)
          : 'no meta',
      });
    }

    return response; // Return the JSON:API response directly
  } catch (error) {
    const totalTime = performance.now() - startTime;
    console.error(
      `💥 API request failed after ${totalTime.toFixed(2)}ms:`,
      error
    );
    throw error;
  }
}

interface FetchFacetValuesParams {
  facetName: string;
  searchParams: URLSearchParams;
  page?: number;
  perPage?: number;
  sort?: FacetValuesSort;
  qFacet?: string;
  options?: FetchOptions;
}

export async function fetchFacetValues({
  facetName,
  searchParams,
  page = 1,
  perPage = 10,
  sort = 'count_desc',
  qFacet,
  options = defaultFetchOptions,
}: FetchFacetValuesParams): Promise<FacetValuesResponse> {
  // Check if we are in the browser
  const isBrowser = typeof window !== 'undefined';

  if (isBrowser) {
    // Client-side: Proxy request through React Router resource route to avoid rate limits
    // The SSR server has the privileged API key
    // Note: Route is /search/facets/:facetName (not /api/v1/...) to go through SSR, not nginx proxy
    const proxyUrl = new URL(
      `/search/facets/${facetName}`,
      window.location.origin
    );

    proxyUrl.searchParams.set('page', Math.max(1, page).toString());
    proxyUrl.searchParams.set(
      'per_page',
      Math.max(1, Math.min(100, perPage)).toString()
    );
    if (sort) proxyUrl.searchParams.set('sort', sort);
    if (qFacet) proxyUrl.searchParams.set('q_facet', qFacet);

    // Forward relevant global search params
    // We only forward what's necessary to filter the facets correctly
    const copyParamKeys = ['q', 'adv_q'] as const;
    copyParamKeys.forEach((key) => {
      const value = searchParams.get(key);
      if (value !== null && value !== '') {
        proxyUrl.searchParams.set(key, value);
      }
    });

    Array.from(searchParams.keys())
      .filter(
        (key) =>
          key.startsWith('include_filters[') ||
          key.startsWith('exclude_filters[') ||
          key.startsWith('fq[')
      )
      .forEach((key) => {
        searchParams.getAll(key).forEach((value) => {
          proxyUrl.searchParams.append(key, value);
        });
      });

    debugLog('🔗 fetchFacetValues Proxy URL:', proxyUrl.toString());

    const response = await fetch(proxyUrl.toString(), {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      // If the proxy fails, we can try to parse the error or just throw
      const errorText = await response.text();
      console.error('Facet proxy error:', errorText);
      throw new Error(`Failed to fetch facet values: ${response.statusText}`);
    }

    const data = await response.json();

    debugLog('📦 fetchFacetValues response from proxy:', {
      hasData: !!data.data,
      dataLength: data.data?.length || 0,
    });

    return data;
  }

  // Server-side (SSR): Call API directly using the server-only key (implied by server environment)
  const apiBasePath = getApiBasePath();
  const baseUrl = `${apiBasePath}/search/facets/${facetName}`;

  const url = createApiUrl(baseUrl);

  const copyParamKeys = ['q', 'adv_q'] as const;
  copyParamKeys.forEach((key) => {
    const value = searchParams.get(key);
    if (value !== null && value !== '') {
      url.searchParams.set(key, value);
    }
  });

  Array.from(searchParams.keys())
    .filter(
      (key) =>
        key.startsWith('include_filters[') ||
        key.startsWith('exclude_filters[') ||
        key.startsWith('fq[')
    )
    .forEach((key) => {
      searchParams.getAll(key).forEach((value) => {
        url.searchParams.append(key, value);
      });
    });

  url.searchParams.set('page', Math.max(1, page).toString());
  url.searchParams.set(
    'per_page',
    Math.max(1, Math.min(100, perPage)).toString()
  );

  if (sort) {
    url.searchParams.set('sort', sort);
  }

  if (qFacet) {
    url.searchParams.set('q_facet', qFacet);
  }

  debugLog('🔗 fetchFacetValues URL (SSR):', url.toString());
  const response = await unifiedFetch<FacetValuesResponse>(
    url.toString(),
    options
  );
  debugLog('📦 fetchFacetValues response (SSR):', {
    hasData: !!response.data,
    dataLength: response.data?.length || 0,
    hasMeta: !!response.meta,
    metaTotalCount: response.meta?.totalCount,
  });
  return response;
}

export async function fetchResourceDetails(
  id: string,
  onApiCall?: (url: string) => void,
  options: FetchOptions = { useJsonp: false } // Always use regular fetch for modern JSON:API
): Promise<GeoDocumentDetails> {
  const apiBasePath = getApiBasePath();
  // Use consistent pattern: apiBasePath/resources/{id}
  // getApiBasePath() returns '/api/v1' for localhost or full URL for production
  const baseUrl = `${apiBasePath}/resources/${id}`;
  const url = createApiUrl(baseUrl);
  onApiCall?.(url.toString());

  try {
    const response = await unifiedFetch<{ data: GeoDocumentDetails }>(
      url.toString(),
      options
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching resource details:', error); // Add debugging
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      `Failed to fetch resource details: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}

export async function fetchFeaturedResourcePreview(
  id: string,
  onApiCall?: (url: string) => void,
  options: FetchOptions = { useJsonp: false }
): Promise<GeoDocumentDetails> {
  const apiBasePath = getApiBasePath();
  const baseUrl = `${apiBasePath}/resources/${id}`;
  const url = createApiUrl(baseUrl);
  url.searchParams.set('ui_profile', 'homepage');
  onApiCall?.(url.toString());

  try {
    const response = await unifiedFetch<{ data: GeoDocumentDetails }>(
      url.toString(),
      options
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching featured resource preview:', error);
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      `Failed to fetch featured resource preview: ${
        error instanceof Error ? error.message : 'Unknown error'
      }`
    );
  }
}

interface Suggestion {
  type: 'suggestion';
  id: string;
  attributes: {
    text: string;
    score: number;
  };
}

interface SuggestResponse {
  data: Suggestion[];
}

export async function fetchHomeBlogPosts(params?: {
  limit?: number;
  theme?: string;
  pinnedSlugs?: string[];
  tag?: string;
}): Promise<HomeBlogPostsResponse> {
  const apiBase = `${getApiBasePath().replace(/\/$/, '')}/home/blog-posts`;
  const candidates: string[] =
    typeof window !== 'undefined'
      ? Array.from(
          new Set([
            '/api/v1/home/blog-posts', // Same-origin API path when app served from API host
            '/home/blog-posts', // SSR proxy route fallback (frontend :3000)
            apiBase, // Absolute/configured API base fallback (e.g. localhost:8000)
          ])
        )
      : [apiBase];

  let lastError: ApiError | null = null;
  const attempted: string[] = [];

  for (const base of candidates) {
    let url: URL;
    try {
      url =
        typeof window !== 'undefined'
          ? new URL(base, window.location.origin)
          : new URL(base);
    } catch (error) {
      lastError = new ApiError(
        `Home blog request failed: ${error instanceof Error ? error.message : 'Invalid URL'}`
      );
      continue;
    }

    if (params?.limit) {
      url.searchParams.set('limit', String(params.limit));
    }
    if (params?.theme) {
      url.searchParams.set('theme', params.theme);
    }
    if (params?.tag) {
      url.searchParams.set('tag', params.tag);
    }
    if (params?.pinnedSlugs?.length) {
      params.pinnedSlugs.forEach((slug) => {
        if (slug) url.searchParams.append('pinned_slugs', slug);
      });
    }
    attempted.push(url.toString());

    try {
      const res = await fetch(url.toString(), {
        headers: { Accept: 'application/json' },
      });
      const contentType = (res.headers.get('content-type') || '').toLowerCase();
      const bodyText = await res.text();
      if (!res.ok) {
        lastError = new ApiError(
          `Home blog request failed (${url.toString()}): ${bodyText}`,
          res.status
        );
        continue;
      }
      // Some dev route fallbacks return HTML with 200 status; treat as miss and continue.
      if (!contentType.includes('application/json')) {
        lastError = new ApiError(
          `Home blog request failed (${url.toString()}): expected JSON but got ${contentType || 'unknown content-type'}`
        );
        continue;
      }
      return JSON.parse(bodyText) as HomeBlogPostsResponse;
    } catch (error) {
      lastError =
        error instanceof ApiError
          ? error
          : new ApiError(
              `Home blog request failed: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
    }
  }

  const attemptedMsg =
    attempted.length > 0 ? ` (attempted: ${attempted.join(', ')})` : '';
  if (lastError) {
    throw new ApiError(`${lastError.message}${attemptedMsg}`, lastError.status);
  }
  throw new ApiError(`Home blog request failed${attemptedMsg}`);
}

export async function fetchSuggestions(
  query: string,
  options: FetchOptions = defaultFetchOptions
): Promise<Suggestion[]> {
  if (!query.trim()) return [];

  const apiBasePath = getApiBasePath();
  // Suggestions are served by the API under the same `/api/v1` prefix.
  const baseUrl = `${apiBasePath}/suggest`;
  const url = createApiUrl(baseUrl);
  url.searchParams.set('q', query);

  try {
    const data = await unifiedFetch<SuggestResponse>(url.toString(), options);
    return data.data.map((suggestion) => ({
      ...suggestion,
      attributes: {
        text: suggestion.attributes.text,
        score: suggestion.attributes.score,
      },
    }));
  } catch (error) {
    console.error('Error fetching suggestions:', error);
    return [];
  }
}

export async function fetchBookmarkedResources(
  ids: string[],
  onApiCall?: (url: string) => void,
  options: FetchOptions = defaultFetchOptions
): Promise<JsonApiResponse> {
  if (ids.length === 0) {
    return {
      jsonapi: { version: '1.0', profile: [] },
      links: { self: '', first: '', last: '' },
      meta: {
        totalCount: 0,
        totalPages: 0,
        currentPage: 1,
        perPage: 10,
        query: '',
      },
      data: [],
      included: [],
    };
  }

  const apiBasePath = getApiBasePath();
  const baseUrl = `${apiBasePath}/search`;
  const url = createApiUrl(baseUrl);

  url.searchParams.set('search_field', 'all_fields');
  url.searchParams.set('q', '');

  ids.forEach((id) => {
    url.searchParams.append('include_filters[id][]', id);
  });

  const finalUrl = url.toString();
  onApiCall?.(finalUrl);

  try {
    const data = await unifiedFetch<JsonApiResponse>(finalUrl, options);

    if (!data.data || !Array.isArray(data.data)) {
      throw new ApiError('Invalid response format from API');
    }

    return data; // Return the JSON:API response directly
  } catch (error) {
    if (error instanceof Error) {
      throw new ApiError(
        `Failed to fetch bookmarked resources: ${error.message}`
      );
    }
    throw new ApiError('Failed to fetch bookmarked resources');
  }
}

export async function fetchGazetteerSearch(
  query: string,
  limit: number = 10,
  offset: number = 0,
  options: FetchOptions = defaultFetchOptions
): Promise<GazetteerResponse> {
  if (!query.trim()) {
    return {
      jsonapi: { version: '1.1', profile: [] },
      links: { self: '' },
      meta: {
        totalCount: 0,
        totalPages: 0,
        currentPage: 1,
        perPage: limit,
        query: '',
        offset: 0,
        gazetteer: 'wof',
      },
      data: [],
    };
  }

  const apiBasePath = getApiBasePath();
  const baseUrl = `${apiBasePath}/gazetteers/wof/search`;

  const url = createApiUrl(baseUrl);
  url.searchParams.set('q', query);
  url.searchParams.set('limit', limit.toString());
  url.searchParams.set('offset', offset.toString());

  try {
    const data = await unifiedFetch<GazetteerResponse>(url.toString(), options);
    return data;
  } catch (error) {
    console.error('Error fetching gazetteer search:', error);
    throw new ApiError('Failed to fetch gazetteer search results');
  }
}

/** API returns hexes as compact [h3, count] tuples (facet-style). We normalize to objects. */
export interface MapH3ResponseRaw {
  resolution: number;
  hexes: Array<[string, number]>;
  globalCount: number;
}

export interface MapH3Response {
  resolution: number;
  hexes: Array<{ h3: string; count: number }>;
  globalCount: number;
}

const MAP_H3_REQUEST_VERSION = '2';

function normalizeMapH3Response(raw: MapH3ResponseRaw): MapH3Response {
  return {
    resolution: raw.resolution,
    globalCount: raw.globalCount,
    hexes: raw.hexes.map(([h3, count]) => ({ h3, count })),
  };
}

/**
 * Fetch H3 hex aggregation for map visualization.
 * Uses the SSR proxy (/map/h3) so requests go through our server with the API key,
 * avoiding rate limits. The proxy and backend both cache aggressively.
 */
export async function fetchMapH3(
  query: string,
  bbox: string | undefined,
  resolution: number,
  queryString?: string
): Promise<MapH3Response> {
  const base =
    typeof window !== 'undefined'
      ? `${window.location.origin}/map/h3`
      : `${getApiBasePath().replace(/\/$/, '')}/map/h3`;
  const url = new URL(base);
  url.searchParams.set('q', query);
  if (bbox != null && bbox !== '') {
    url.searchParams.set('bbox', bbox);
  }
  url.searchParams.set('resolution', String(resolution));
  // Bump the request URL when client-side hex semantics change so stale browser cache
  // entries from previous builds do not override the latest search constraints.
  url.searchParams.set('_v', MAP_H3_REQUEST_VERSION);
  if (queryString) {
    const params = new URLSearchParams(queryString);
    for (const [k, v] of params) {
      if (k !== 'q' && k !== 'bbox' && k !== 'resolution')
        url.searchParams.append(k, v);
    }
  }
  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
    mode: 'cors',
    credentials: 'omit',
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(`Map H3 request failed: ${text}`, res.status);
  }
  const raw = (await res.json()) as MapH3ResponseRaw;
  return normalizeMapH3Response(raw);
}

function emptyNominatimResponse(
  query: string,
  limit: number
): GazetteerResponse {
  return {
    jsonapi: { version: '1.1', profile: [] },
    links: { self: '' },
    meta: {
      totalCount: 0,
      totalPages: 0,
      currentPage: 1,
      perPage: limit,
      query,
      offset: 0,
      gazetteer: 'nominatim',
    },
    data: [],
  };
}

export async function fetchNominatimSearch(
  query: string,
  limit: number = 5
): Promise<GazetteerResponse> {
  const normalizedQuery = query.trim().replace(/\s+/g, ' ');
  const normalizedLimit = Math.max(1, Math.min(limit, 5));

  if (!normalizedQuery) {
    return emptyNominatimResponse('', normalizedLimit);
  }

  const base =
    typeof window !== 'undefined'
      ? `${window.location.origin}/places/suggest`
      : 'http://localhost/places/suggest';
  const url = new URL(base);
  url.searchParams.set('q', normalizedQuery);
  url.searchParams.set('limit', normalizedLimit.toString());

  try {
    const response = await fetch(url.toString(), {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    });

    if (!response.ok) {
      throw new ApiError(
        `Nominatim proxy error: ${response.status}`,
        response.status
      );
    }

    return (await response.json()) as GazetteerResponse;
  } catch (error) {
    console.error('Error fetching Nominatim search:', error);
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError('Failed to fetch Nominatim search results');
  }
}
