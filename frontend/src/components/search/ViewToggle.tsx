import React from 'react';
import { List, Grid, Map } from 'lucide-react';

export type ViewMode = 'list' | 'gallery' | 'map';

interface ViewToggleProps {
  currentView: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

export function ViewToggle({ currentView, onViewChange }: ViewToggleProps) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex rounded-md shadow-sm" role="group">
        <button
          type="button"
          onClick={() => onViewChange('list')}
          className={`px-3 py-2 text-sm font-medium border rounded-l-lg hover:bg-gray-100 focus:z-10 focus:ring-2 focus:ring-blue-700 focus:text-blue-700 ${
            currentView === 'list'
              ? 'bg-blue-50 text-blue-700 border-blue-200'
              : 'bg-white text-gray-900 border-gray-200 hover:text-blue-700'
          }`}
          title="List View"
        >
          <List className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => onViewChange('gallery')}
          className={`px-3 py-2 text-sm font-medium border-t border-b hover:bg-gray-100 focus:z-10 focus:ring-2 focus:ring-blue-700 focus:text-blue-700 ${
            currentView === 'gallery'
              ? 'bg-blue-50 text-blue-700 border-blue-200'
              : 'bg-white text-gray-900 border-gray-200 hover:text-blue-700'
          }`}
          title="Gallery View"
        >
          <Grid className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => onViewChange('map')}
          className={`px-3 py-2 text-sm font-medium border rounded-r-lg hover:bg-gray-100 focus:z-10 focus:ring-2 focus:ring-blue-700 focus:text-blue-700 ${
            currentView === 'map'
              ? 'bg-blue-50 text-blue-700 border-blue-200'
              : 'bg-white text-gray-900 border-gray-200 hover:text-blue-700'
          }`}
          title="Map View"
        >
          <Map className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
