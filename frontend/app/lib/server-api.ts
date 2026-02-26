/**
 * Server-side API utilities for React Router v7.
 * These functions run only on the server and can access environment variables
 * with the API key, which is never exposed to the client.
 */

// Minimal Node-ish env typing without pulling in @types/node.
declare const process: { env: Record<string, string | undefined> };

// Docker sets API_BASE_URL=http://api:8000/api/v1; fallback for local preview/start
const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000/api/v1";
const API_KEY = process.env.BTAA_GEOSPATIAL_API_KEY;

function applyDefaultQueryParams(url: URL, defaults: string[] | undefined) {
  if (!defaults || defaults.length === 0) return;
  defaults.forEach((param) => {
    if (!param) return;
    const parsed = new URLSearchParams(param);
    parsed.forEach((value, key) => {
      // Avoid duplicate entries if caller already set the same value.
      const existing = url.searchParams.getAll(key);
      if (existing.includes(value)) return;
      url.searchParams.append(key, value);
    });
  });
}

/**
 * Makes a server-side fetch request to the API with the API key.
 * This function should only be called from React Router v7 loaders/actions.
 */
export async function serverFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  // If caller passes a fully-qualified URL (e.g. serverFetchWithTheme builds one so it can
  // safely append query params), do NOT prefix API_BASE_URL again.
  const isAbsoluteUrl =
    endpoint.startsWith("http://") || endpoint.startsWith("https://");

  const url = isAbsoluteUrl
    ? endpoint
    : endpoint.startsWith("/")
      ? `${API_BASE_URL}${endpoint}`
      : `${API_BASE_URL}/${endpoint}`;

  const headers = new Headers(options.headers);
  // Default to JSON:API unless caller provided an Accept header (e.g., for images).
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/vnd.api+json, application/json");
  }

  if (API_KEY) {
    headers.set("X-API-Key", API_KEY);
  }

  return fetch(url, {
    ...options,
    headers,
  });
}

/**
 * Theme-aware server fetch: applies theme.yaml default_query_params based on request cookie/query.
 * Use this for search/home endpoints where institution scoping matters.
 */
export async function serverFetchWithTheme(
  request: Request,
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  // Build absolute API URL first (so we can safely append params).
  const base = endpoint.startsWith("/")
    ? `${API_BASE_URL}${endpoint}`
    : `${API_BASE_URL}/${endpoint}`;

  const url = new URL(base);
  const { getThemeConfigFromRequest } = await import("./theme.server");
  const theme = getThemeConfigFromRequest(request);
  applyDefaultQueryParams(url, theme.api?.default_query_params);

  // Ensure we call the normal serverFetch logic so headers/API key are correct.
  // Pass the final URL as a full string endpoint.
  return serverFetch(url.toString(), options);
}

/**
 * Helper to parse JSON responses from the API.
 */
export async function serverFetchJson<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await serverFetch(endpoint, options);
  if (!response.ok) {
    throw new Response(
      `API request failed: ${response.status} ${response.statusText}`,
      { status: response.status }
    );
  }
  return response.json();
}

export async function serverFetchJsonWithTheme<T>(
  request: Request,
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await serverFetchWithTheme(request, endpoint, options);
  if (!response.ok) {
    throw new Response(
      `API request failed: ${response.status} ${response.statusText}`,
      { status: response.status }
    );
  }
  return response.json();
}
