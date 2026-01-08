/**
 * Server-side API utilities for React Router v7.
 * These functions run only on the server and can access environment variables
 * with the API key, which is never exposed to the client.
 */

const API_BASE_URL = process.env.API_BASE_URL || "http://api:8000/api/v1";
const API_KEY = process.env.BTAA_GEOSPATIAL_API_KEY;

/**
 * Makes a server-side fetch request to the API with the API key.
 * This function should only be called from React Router v7 loaders/actions.
 */
export async function serverFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = endpoint.startsWith("/")
    ? `${API_BASE_URL}${endpoint}`
    : `${API_BASE_URL}/${endpoint}`;

  const headers = new Headers(options.headers);
  headers.set("Accept", "application/vnd.api+json, application/json");

  if (API_KEY) {
    headers.set("X-API-Key", API_KEY);
  }

  return fetch(url, {
    ...options,
    headers,
  });
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
