import React from 'react';
import { ChevronDown } from 'lucide-react';

interface SortOption {
  id: string;
  label: string;
  url: string;
}

interface SortControlProps {
  options: SortOption[];
  currentSort: string;
  onSortChange: (sortId: string) => void;
}

export function SortControl({
  options,
  currentSort,
  onSortChange,
}: SortControlProps) {
  if (!options || options.length === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="sort-select" className="text-sm text-gray-600">
        Sort by:
      </label>
      <div className="relative">
        <select
          id="sort-select"
          value={currentSort}
          onChange={(e) => onSortChange(e.target.value)}
          className="appearance-none bg-white border border-gray-300 rounded-md py-1.5 pl-3 pr-8 text-sm leading-6 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
      </div>
    </div>
  );
}
