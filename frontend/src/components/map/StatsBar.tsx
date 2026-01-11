// Summary bar displaying current query, total resources, and count of features for level
import type { ZoomLevel, GeoFacetItem } from '../../types/map';
import { formatCount } from '../../utils/formatNumber';

interface Props {
  zoomLevel: ZoomLevel;
  dataForLevel: GeoFacetItem[];
  totalResources: number;
  query: string;
}

export function StatsBar({
  zoomLevel,
  dataForLevel,
  totalResources,
  query,
}: Props) {
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
              : 'Counties'}
          :<span className="font-semibold"> {formatCount(dataForLevel.length)}</span>
        </div>
      </div>
      <div className="ml-auto text-right">
        <p className="text-xs text-gray-500">
          Click on any region to view details
        </p>
      </div>
    </div>
  );
}
