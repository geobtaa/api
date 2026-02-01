// Summary bar displaying current query, total resources, and count of features for level
import { Link } from 'react-router';
import type { ZoomLevel, GeoFacetItem } from '../../types/map';
import { formatCount } from '../../utils/formatNumber';

interface Props {
  zoomLevel: ZoomLevel;
  dataForLevel: GeoFacetItem[];
  totalResources: number;
  query: string;
  globalCount?: number;
  hexCount?: number;
  hexTotalInView?: number;
  hexLoading?: boolean;
  hexError?: string | null;
}

export function StatsBar({
  zoomLevel,
  dataForLevel,
  totalResources,
  query,
  globalCount = 0,
  hexCount = 0,
  hexTotalInView = 0,
  hexLoading = false,
  hexError = null,
}: Props) {
  const searchParams = new URLSearchParams();
  if (query) searchParams.set('q', query);
  searchParams.set('include_filters[geo_global][]', 'true');
  const globalSearchUrl = `/search?${searchParams.toString()}`;

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="text-sm text-gray-600">
        <div>
          Current Query:{' '}
          <span className="font-semibold">"{query || 'All Resources'}"</span>
        </div>
        <div>
          Total Resources:{' '}
          <span className="font-semibold">{formatCount(totalResources)}</span>
        </div>
        <div>
          {zoomLevel === 'country'
            ? 'Countries'
            : zoomLevel === 'region'
              ? 'Regions'
              : zoomLevel === 'hex'
                ? 'Hexes'
                : 'Counties'}
          :
          <span className="font-semibold">
            {' '}
            {zoomLevel === 'hex'
              ? formatCount(hexCount)
              : formatCount(dataForLevel.length)}
          </span>
          {zoomLevel === 'hex' && hexTotalInView > 0 && (
            <>
              {' '}
              ·{' '}
              <span className="font-semibold">
                {formatCount(hexTotalInView)}
              </span>{' '}
              in view
            </>
          )}
        </div>
        {zoomLevel === 'hex' && hexLoading && (
          <div className="text-amber-600 text-sm">Loading hex grid…</div>
        )}
        {zoomLevel === 'hex' && hexError && (
          <div className="text-red-600 text-sm">{hexError}</div>
        )}
        {globalCount > 0 && (
          <div>
            Global:{' '}
            <Link
              to={globalSearchUrl}
              className="font-semibold text-blue-600 hover:text-blue-800 hover:underline"
            >
              {formatCount(globalCount)} resources
            </Link>
          </div>
        )}
      </div>
      <div className="ml-auto text-right">
        <p className="text-xs text-gray-500">
          Click on any region to view details
        </p>
      </div>
    </div>
  );
}
