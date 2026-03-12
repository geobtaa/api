/**
 * Builds the search URL for a single H3 cell, preserving existing query params
 * and adding the H3 filter for the given resolution.
 */
export function buildSearchUrl(
  h3: string,
  resolution: number,
  searchQuery?: string,
  queryString?: string
): string {
  return buildSearchUrlForHexes([h3], resolution, searchQuery, queryString);
}

/**
 * Builds the search URL for multiple H3 cells, preserving existing query params
 * and adding H3 filters for the given resolution.
 * Caps at maxHexes to avoid very long URLs (default 50).
 */
export function buildSearchUrlForHexes(
  hexes: string[],
  resolution: number,
  searchQuery?: string,
  queryString?: string,
  maxHexes = 50
): string {
  const params = new URLSearchParams(
    typeof queryString === 'string' && queryString.startsWith('?')
      ? queryString.slice(1)
      : (queryString ?? '')
  );
  if (searchQuery) params.set('q', searchQuery);
  // Remove any existing H3 filters
  Array.from(params.keys())
    .filter((k) => k.startsWith('include_filters[h3_res'))
    .forEach((k) => params.delete(k));
  const key = `include_filters[h3_res${resolution}][]`;
  const toAdd = hexes.slice(0, maxHexes);
  for (const h3 of toAdd) {
    params.append(key, h3);
  }
  params.delete('page');
  return `/search?${params.toString()}`;
}
