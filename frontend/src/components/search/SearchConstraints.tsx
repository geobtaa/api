import { useSearchParams } from 'react-router';
import { X, Search, XCircle } from 'lucide-react';
import type { AdvancedClause, FacetFilter } from '../../types/search';
import { getFacetLabel } from '../../utils/facetLabels';
import { humanizeFieldName } from '../../constants/fieldLabels';

interface SearchConstraintsProps {
  facets: FacetFilter[];
  excludeFacets?: FacetFilter[];
  advancedClauses?: AdvancedClause[];
  query?: string;
  onRemoveFacet: (facet: FacetFilter) => void;
  onRemoveExclude?: (facet: FacetFilter) => void;
  onRemoveAdvancedClause?: (clause: AdvancedClause, index: number) => void;
  onRemoveQuery: () => void;
  onClearAll: () => void;
}

export function SearchConstraints({
  facets,
  excludeFacets = [],
  query,
  advancedClauses = [],
  onRemoveFacet,
  onRemoveExclude,
  onRemoveAdvancedClause,
  onRemoveQuery,
  onClearAll,
}: SearchConstraintsProps) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Check for geo filter (bbox)
  const geoType = searchParams.get('include_filters[geo][type]');
  const hasGeoFilter = geoType === 'bbox';

  // Parse bbox coordinates
  const getBBoxDisplay = (): string | null => {
    if (!hasGeoFilter) return null;

    const topLeftLat = searchParams.get('include_filters[geo][top_left][lat]');
    const topLeftLon = searchParams.get('include_filters[geo][top_left][lon]');
    const bottomRightLat = searchParams.get(
      'include_filters[geo][bottom_right][lat]'
    );
    const bottomRightLon = searchParams.get(
      'include_filters[geo][bottom_right][lon]'
    );

    if (topLeftLat && topLeftLon && bottomRightLat && bottomRightLon) {
      // Format as N E S W (North, East, South, West)
      // top_left is northwest (N, W)
      // bottom_right is southeast (S, E)
      const n = parseFloat(topLeftLat).toFixed(2);
      const e = parseFloat(bottomRightLon).toFixed(2);
      const s = parseFloat(bottomRightLat).toFixed(2);
      const w = parseFloat(topLeftLon).toFixed(2);

      return `BBox: ${n}°N ${e}°E ${s}°S ${w}°W`;
    }
    return null;
  };

  const handleRemoveGeoFilter = () => {
    const newParams = new URLSearchParams(searchParams);
    // Remove all geo filter params
    Array.from(newParams.keys())
      .filter((key) => key.startsWith('include_filters[geo]'))
      .forEach((key) => newParams.delete(key));
    newParams.delete('page');
    setSearchParams(newParams);
  };

  const bboxDisplay = getBBoxDisplay();

  if (
    facets.length === 0 &&
    excludeFacets.length === 0 &&
    !query &&
    advancedClauses.length === 0 &&
    !hasGeoFilter
  ) {
    return null;
  }

  return (
    <div className="mt-4 mb-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-medium text-gray-500">Active Filters:</h2>
        {query && (
          <button
            onClick={onRemoveQuery}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
          >
            <Search size={14} className="text-blue-500" />
            <span className="text-sm">Search: {query}</span>
            <X size={14} className="text-blue-500" />
          </button>
        )}
        {hasGeoFilter && bboxDisplay && (
          <button
            onClick={handleRemoveGeoFilter}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
            title="Remove location filter"
          >
            <span className="text-sm">{bboxDisplay}</span>
            <X size={14} className="text-blue-500" />
          </button>
        )}
        {facets
          .filter(
            (facet) =>
              !facet.field.startsWith('geo') && facet.field !== 'year_range'
          ) // Filter out geo and year_range
          .map((facet, index) => (
            <button
              key={`${facet.field}-${index}`}
              onClick={() => onRemoveFacet(facet)}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
            >
              <span className="text-sm">
                {getFacetLabel(facet.field)}: {facet.value}
              </span>
              <X size={14} className="text-blue-500" />
            </button>
          ))}
        {/* Helper to display merged Year Range */}
        {(() => {
          // We look for year_range filters in the facets list to know values,
          // OR we parse from URL params directly?
          // Facets prop comes from SearchPage parsing. Let's look at `facets` prop.
          // It likely contains { field: 'year_range', value: '...' }?
          // Actually, the search service/page might be passing it weirdly if it's nested structure.
          // Let's rely on URL params to be safe, or check how `facets` are populated.
          // The facets list in props is likely flat value lists.
          // Given the user request "year_range: 1910 | year_range: 1932", it suggests they come as separate items.

          const rangeFacets = facets.filter((f) => f.field === 'year_range');
          if (rangeFacets.length === 0) return null;

          // We expect potentially two items, one for start and one for end,
          // BUT the value might be just the number.
          // We need to know which is which?
          // Actually, looking at the URL: ?include_filters[year_range][start]=1910...
          // The "facets" prop passed here probably comes from `SearchPage` parsing params.
          // If `SearchPage` blindly pushes keys/values, we might not know which is start/end just from value.
          // BEST APPROACH: Read from URL params directly for this specific compound filter.

          const start = searchParams.get('include_filters[year_range][start]');
          const end = searchParams.get('include_filters[year_range][end]');

          if (!start && !end) return null;

          const label = `Year Range: ${start || '?'} - ${end || '?'}`;

          return (
            <button
              onClick={() => {
                const newParams = new URLSearchParams(searchParams);
                newParams.delete('include_filters[year_range][start]');
                newParams.delete('include_filters[year_range][end]');
                // Also maintain others? setParams triggers navigation
                setSearchParams(newParams);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
            >
              <span className="text-sm">{label}</span>
              <X size={14} className="text-blue-500" />
            </button>
          );
        })()}
        {excludeFacets.map((facet, index) => (
          <button
            key={`exclude-${facet.field}-${index}`}
            onClick={() => {
              // Prefer parent handler if provided
              onRemoveExclude?.(facet);

              // Also ensure URL params update locally in case parent doesn't modify them
              const params = new URLSearchParams(searchParams);
              const key = `exclude_filters[${facet.field}][]`;
              const current = params.getAll(key);
              if (current.length > 0) {
                params.delete(key);
                current
                  .filter((v) => v !== facet.value)
                  .forEach((v) => params.append(key, v));
                setSearchParams(params);
              }
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-50 text-red-700 hover:bg-red-100 transition-colors"
            title="Remove exclusion"
          >
            <span className="text-sm">
              Exclude {getFacetLabel(facet.field)}: {facet.value}
            </span>
            <X size={14} className="text-red-500" />
          </button>
        ))}
        {advancedClauses.map((clause, index) => (
          <button
            key={`advanced-${index}-${clause.field}-${clause.q}`}
            onClick={() => onRemoveAdvancedClause?.(clause, index)}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full transition-colors ${
              clause.op === 'NOT'
                ? 'bg-red-50 text-red-700 hover:bg-red-100'
                : 'bg-purple-50 text-purple-700 hover:bg-purple-100'
            }`}
            title={`${clause.op} ${clause.field}`}
          >
            <span className="text-sm">
              {clause.op} {humanizeFieldName(clause.field)}: {clause.q}
            </span>
            <X
              size={14}
              className={
                clause.op === 'NOT' ? 'text-red-500' : 'text-purple-500'
              }
            />
          </button>
        ))}
        <button
          onClick={onClearAll}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-gray-50 text-gray-700 hover:bg-gray-100 transition-colors"
        >
          <XCircle size={14} className="text-gray-500" />
          <span className="text-sm">Clear All</span>
        </button>
      </div>
    </div>
  );
}
