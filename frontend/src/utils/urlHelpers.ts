import { ParsedFacet } from '../types/api';

export function parseFacetUrl(url: string): ParsedFacet | null {
  try {
    const urlObj = new URL(url, 'https://geo.btaa.org');

    // Handle relative URLs that start with /catalog
    if (url.startsWith('/catalog')) {
      const params = new URLSearchParams(urlObj.search);

      // Extract facet parameters (f[field][])
      for (const [key, value] of params.entries()) {
        if (key.startsWith('f[') && key.endsWith('][]')) {
          const field = key.slice(2, -3); // Remove 'f[' and '][]'
          return {
            field,
            value: decodeURIComponent(value),
          };
        }
      }
    }
  } catch (error) {
    console.error('Error parsing facet URL:', error);
  }

  return null;
}

export function createFacetSearchUrl(field: string, value: string): string {
  const url = new URL('https://geo.btaa.org/');
  url.searchParams.set('format', 'json');
  url.searchParams.set('search_field', 'all_fields');
  url.searchParams.append(`f[${field}][]`, value);
  return url.toString();
}
