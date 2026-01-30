// Legend component visualizes the color scale used for resource density (blue ramp, BTAA dark blue = high)
const HEX_COLOR_HIGH = '#003C5B';

function getColor(intensity: number): string {
  return intensity > 0.8
    ? HEX_COLOR_HIGH
    : intensity > 0.6
      ? '#1E40AF'
      : intensity > 0.4
        ? '#2563EB'
        : intensity > 0.2
          ? '#3B82F6'
          : intensity > 0.1
            ? '#60A5FA'
            : intensity > 0
              ? '#93C5FD'
              : '#DBEAFE';
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
          {[0, 0.1, 0.2, 0.4, 0.6, 0.8, 1].map((intensity) => (
            <div
              key={intensity}
              className="w-4 h-4"
              style={{ backgroundColor: getColor(intensity) }}
              title={`${Math.round(intensity * 100)}%`}
            />
          ))}
        </div>
        <span className="text-xs text-gray-600">High</span>
      </div>
    </div>
  );
}
