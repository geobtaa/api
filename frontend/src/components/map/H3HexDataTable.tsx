import { Link } from 'react-router';
import { formatCount } from '../../utils/formatNumber';
import { buildSearchUrl } from '../../utils/h3SearchUrl';

export interface H3HexDataTableProps {
  hexes: Array<{ h3: string; count: number }>;
  resolution: number;
  searchQuery?: string;
  queryString?: string;
  loading?: boolean;
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
                    to={buildSearchUrl(
                      h3,
                      resolution,
                      searchQuery,
                      queryString
                    )}
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
