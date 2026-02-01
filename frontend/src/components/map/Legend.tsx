// Legend component visualizes the color scale used for resource density (blue ramp, BTAA dark blue = high)
const HEX_RAMP_COLORS = [
  '#DBEAFE',
  '#BFDBFE',
  '#93C5FD',
  '#7AB3FD',
  '#60A5FA',
  '#3B82F6',
  '#2563EB',
  '#1D4ED8',
  '#1E40AF',
  '#003C5B',
];
const HEX_RAMP_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];

function getColor(intensity: number): string {
  for (let i = 0; i < HEX_RAMP_THRESHOLDS.length; i++) {
    if (intensity <= HEX_RAMP_THRESHOLDS[i]) return HEX_RAMP_COLORS[i];
  }
  return HEX_RAMP_COLORS[HEX_RAMP_COLORS.length - 1];
}

export function Legend() {
  return (
    <div className="mt-4 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-3">
        Resource Density
      </h3>
      <div className="flex items-center space-x-2">
        <span className="text-xs text-gray-600">Low</span>
        <div className="flex space-x-1">
          {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].map(
            (intensity) => (
              <div
                key={intensity}
                className="w-4 h-4"
                style={{ backgroundColor: getColor(intensity) }}
                title={`${Math.round(intensity * 100)}%`}
              />
            )
          )}
        </div>
        <span className="text-xs text-gray-600">High</span>
      </div>
    </div>
  );
}
