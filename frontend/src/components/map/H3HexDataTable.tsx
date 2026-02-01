import { Link } from 'react-router';
import { formatCount } from '../../utils/formatNumber';

export interface H3HexDataTableProps {
  hexes: Array<{ h3: string; count: number }>;
  resolution: number;
  searchQuery?: string;
  queryString?: string;
  loading?: boolean;
}

/**
 * Builds the search URL for a given H3 cell, preserving existing query params
 * and adding the H3 filter for the given resolution.
 */
function buildSearchUrl(
  h3: string,
  resolution: number,
  searchQuery?: string,
  queryString?: string
): string {
  const params = new URLSearchParams(
    typeof queryString === 'string' && queryString.startsWith('?')
      ? queryString.slice(1)
      : queryString ?? ''
  );
  if (searchQuery) params.set('q', searchQuery);
  // Remove any existing H3 filters and set this hex
  Array.from(params.keys())
    .filter((k) => k.startsWith('include_filters[h3_res'))
    .forEach((k) => params.delete(k));
  params.set(`include_filters[h3_res${resolution}][]`, h3);
  params.delete('page');
  return `/search?${params.toString()}`;
}

/**
 * Accessible data table presenting H3 hex grid data as an alternative to the map.
 * WCAG 2.2 AA: equivalent alternative (1.1.1), keyboard accessible (2.1.1).
 */
export function H3HexDataTable({
  hexes,
  resolution,
  searchQuery,
  queryString,
  loading = false,
}: H3HexDataTableProps) {
  return (
    <div
      role="region"
      aria-label="H3 hex grid data (alternative to map)"
      className="overflow-auto rounded-lg border border-gray-200 bg-white"
    >
      <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
        <caption className="sr-only">
          Resource count by H3 hex in current map view
        </caption>
        <thead>
          <tr className="bg-gray-50">
            <th scope="col" className="px-4 py-2 font-semibold text-gray-900">
              H3 index
            </th>
            <th scope="col" className="px-4 py-2 font-semibold text-gray-900">
              Resource count
            </th>
            <th scope="col" className="px-4 py-2 font-semibold text-gray-900">
              Action
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {loading ? (
            <tr>
              <td colSpan={3} className="px-4 py-4 text-gray-500">
                Loading hex data…
              </td>
            </tr>
          ) : hexes.length === 0 ? (
            <tr>
              <td colSpan={3} className="px-4 py-4 text-gray-500">
                No hex data in view. Pan or zoom the map to load hexes.
              </td>
            </tr>
          ) : (
            hexes.map(({ h3, count }) => (
              <tr key={h3} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-gray-700">{h3}</td>
                <td className="px-4 py-2 text-gray-700">
                  {formatCount(count)}
                </td>
                <td className="px-4 py-2">
                  <Link
                    to={buildSearchUrl(h3, resolution, searchQuery, queryString)}
                    className="text-blue-600 hover:underline"
                  >
                    Search this hex
                  </Link>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
