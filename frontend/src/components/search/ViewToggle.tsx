import { List, Grid, Map } from 'lucide-react';

export type ViewMode = 'list' | 'gallery' | 'map';

interface ViewToggleProps {
  currentView: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

const VIEW_OPTIONS: Array<{
  mode: ViewMode;
  label: string;
  title: string;
  Icon: typeof Map;
}> = [
  { mode: 'map', label: 'Map', title: 'Map View', Icon: Map },
  { mode: 'list', label: 'List', title: 'List View', Icon: List },
  { mode: 'gallery', label: 'Gallery', title: 'Gallery View', Icon: Grid },
];

export function ViewToggle({ currentView, onViewChange }: ViewToggleProps) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="inline-flex rounded-md shadow-sm"
        role="group"
        aria-label="Search result view"
      >
        {VIEW_OPTIONS.map(({ mode, label, title, Icon }, index) => {
          const isActive = currentView === mode;
          const isFirst = index === 0;
          const isLast = index === VIEW_OPTIONS.length - 1;

          return (
            <button
              key={mode}
              type="button"
              onClick={() => onViewChange(mode)}
              aria-label={`${label} view`}
              aria-pressed={isActive}
              className={`inline-flex items-center gap-2 whitespace-nowrap border px-3 py-2 text-sm font-medium hover:bg-gray-100 focus:z-10 focus:ring-2 focus:ring-blue-700 focus:text-blue-700 ${
                isFirst ? 'rounded-l-lg' : '-ml-px'
              } ${isLast ? 'rounded-r-lg' : ''} ${
                isActive
                  ? 'bg-blue-50 text-blue-700 border-blue-200'
                  : 'bg-white text-gray-900 border-gray-200 hover:text-blue-700'
              }`}
              title={title}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span className="hidden lg:inline">{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
