// Control group for toggling the emphasized geographic level in the UI
import type { ZoomLevel } from '../../types/map';

interface Props {
  zoomLevel: ZoomLevel;
  onChange: (level: ZoomLevel) => void;
}

export function ZoomLevelControls({ zoomLevel, onChange }: Props) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            Geographic Level
          </h3>
          <div className="flex space-x-2">
            {(['country', 'region', 'county', 'hex'] as ZoomLevel[]).map(
              (level) => (
                <button
                  key={level}
                  onClick={() => onChange(level)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    zoomLevel === level
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {level === 'country' && 'Country'}
                  {level === 'region' && 'Region (State)'}
                  {level === 'county' && 'County'}
                  {level === 'hex' && 'Hex'}
                </button>
              )
            )}
          </div>
        </div>
        <div className="text-sm text-gray-600">
          <div>
            Current Level:{' '}
            <span className="font-semibold capitalize">{zoomLevel}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
