// Displays details for the feature last clicked on any of the maps
import { formatCount } from '../../utils/formatNumber';

interface Props {
  name: string;
  hits: number;
  level: 'country' | 'region' | 'county';
}

export function SelectedFeaturePanel({ name, hits, level }: Props) {
  return (
    <div className="mt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">{name}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <dt className="text-sm font-medium text-gray-500">Resources</dt>
          <dd className="text-lg font-semibold text-gray-900">
            {formatCount(hits)}
          </dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-gray-500">
            Geographic Level
          </dt>
          <dd className="text-lg font-semibold text-gray-900 capitalize">
            {level === 'country'
              ? 'Country'
              : level === 'region'
                ? 'Region (State)'
                : 'County'}
          </dd>
        </div>
      </div>
    </div>
  );
}
