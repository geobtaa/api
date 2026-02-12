import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  MinusCircle,
  PlusCircle,
  Search,
  X,
} from 'lucide-react';
import { LightboxModal } from '../ui/LightboxModal';
import { useSearchParams } from 'react-router';
import { useFacetModal } from '../../hooks/useFacetModal';
import type { FacetValuesSort } from '../../types/api';
import { getFacetLabel, normalizeFacetId } from '../../utils/facetLabels';
import { getFacetValueDisplayLabel } from '../../utils/facetDisplay';
import { humanizeFieldName } from '../../constants/fieldLabels';
import { formatCount } from '../../utils/formatNumber';

interface FacetMoreModalProps {
  facetId: string;
  facetLabel: string;
  isOpen: boolean;
  onClose: () => void;
  searchParams: URLSearchParams;
  onToggleInclude: (value: string | number) => void;
  onToggleExclude: (value: string | number) => void;
  onToggleFacetInclude: (field: string, value: string | number) => void;
  onToggleFacetExclude: (field: string, value: string | number) => void;
  isValueIncluded: (value: string | number) => boolean;
  isValueExcluded: (value: string | number) => boolean;
}

const SORT_OPTIONS: Array<{ value: FacetValuesSort; label: string }> = [
  { value: 'count_desc', label: 'Result Count (High → Low)' },
  { value: 'count_asc', label: 'Result Count (Low → High)' },
  { value: 'alpha_asc', label: 'Facet Value (A → Z)' },
  { value: 'alpha_desc', label: 'Facet Value (Z → A)' },
];

export function FacetMoreModal({
  facetId,
  facetLabel,
  isOpen,
  onClose,
  searchParams: searchParamsProp,
  onToggleInclude,
  onToggleExclude,
  onToggleFacetInclude,
  onToggleFacetExclude,
  isValueIncluded,
  isValueExcluded,
}: FacetMoreModalProps) {
  const [, setSearchParams] = useSearchParams();
  const {
    items,
    meta,
    isLoading,
    error,
    hasLoaded,
    page,
    sort,
    qFacet,
    setPage,
    setSort,
    setFacetQuery,
    resetFacetQuery,
  } = useFacetModal({
    facetId,
    isOpen,
    searchParams: searchParamsProp,
  });

  // Handler to remove geo bbox filter (matches SearchConstraints)
  const handleRemoveGeoFilter = () => {
    const params = new URLSearchParams(searchParamsProp);
    Array.from(params.keys())
      .filter((key) => key.startsWith('include_filters[geo]'))
      .forEach((key) => params.delete(key));
    params.delete('page');
    setSearchParams(params);
  };

  // Handler to remove year range filter (matches SearchConstraints)
  const handleRemoveYearRange = () => {
    const params = new URLSearchParams(searchParamsProp);
    params.delete('include_filters[year_range][start]');
    params.delete('include_filters[year_range][end]');
    params.delete('page');
    setSearchParams(params);
  };

  // Handler to remove an advanced clause
  const handleRemoveAdvancedClause = (clauseIndex: number) => {
    const params = new URLSearchParams(searchParamsProp);
    const advQValue = params.get('adv_q');
    if (!advQValue) return;

    try {
      const parsed = JSON.parse(advQValue);
      if (Array.isArray(parsed) && parsed.length > clauseIndex) {
        // Remove the clause at the specified index
        const updated = parsed.filter(
          (_: unknown, index: number) => index !== clauseIndex
        );

        if (updated.length > 0) {
          params.set('adv_q', JSON.stringify(updated));
        } else {
          params.delete('adv_q');
        }
        params.delete('page');
        setSearchParams(params);
      }
    } catch (e) {
      console.warn('Failed to parse adv_q when removing clause:', e);
    }
  };

  const [searchInput, setSearchInput] = useState('');

  useEffect(() => {
    setSearchInput(qFacet);
  }, [qFacet]);

  const totalPages = meta?.totalPages ?? 1;
  const totalCount = meta?.totalCount ?? items.length;
  const isInitialLoading = isLoading && !hasLoaded;
  const isRefetching = isLoading && hasLoaded;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFacetQuery(searchInput.trim());
  };

  const handleClearSearch = () => {
    setSearchInput('');
    resetFacetQuery();
  };

  const emptyStateMessage = useMemo(() => {
    if (isLoading) return 'Loading facet values...';
    if (qFacet) return 'No facet values match your filter.';
    return 'No facet values available.';
  }, [isLoading, qFacet]);

  // Build search context entries to match SearchConstraints display exactly
  const searchContextEntries = useMemo(() => {
    const entries: Array<{
      type: 'query' | 'geo' | 'year_range' | 'include' | 'exclude' | 'advanced';
      label: string;
      value: string;
      fieldId?: string;
      clauseIndex?: number;
      clauseData?: { op: string; f: string; q: string };
      displayValue?: string; // For geo/year_range: full display string
    }> = [];
    const seen = new Set<string>();

    // 1. Search query (matches SearchConstraints)
    const queryValue = searchParamsProp.get('q');
    if (queryValue) {
      entries.push({
        type: 'query',
        label: 'Search',
        value: queryValue,
      });
    }

    // 2. Geo bbox - single entry "BBox: N°N E°E S°S W°W" (matches SearchConstraints)
    const geoType = searchParamsProp.get('include_filters[geo][type]');
    if (geoType === 'bbox') {
      const topLeftLat = searchParamsProp.get(
        'include_filters[geo][top_left][lat]'
      );
      const topLeftLon = searchParamsProp.get(
        'include_filters[geo][top_left][lon]'
      );
      const bottomRightLat = searchParamsProp.get(
        'include_filters[geo][bottom_right][lat]'
      );
      const bottomRightLon = searchParamsProp.get(
        'include_filters[geo][bottom_right][lon]'
      );
      if (topLeftLat && topLeftLon && bottomRightLat && bottomRightLon) {
        const n = parseFloat(topLeftLat).toFixed(2);
        const e = parseFloat(bottomRightLon).toFixed(2);
        const s = parseFloat(bottomRightLat).toFixed(2);
        const w = parseFloat(topLeftLon).toFixed(2);
        entries.push({
          type: 'geo',
          label: 'BBox',
          value: 'bbox',
          displayValue: `${n}°N ${e}°E ${s}°S ${w}°W`,
        });
      }
    }

    // 3. Regular include facets (exclude geo and year_range - handled above)
    const addFacetEntries = (
      prefix: 'include_filters[' | 'exclude_filters[' | 'fq[',
      type: 'include' | 'exclude'
    ) => {
      Array.from(searchParamsProp.keys())
        .filter((key) => key.startsWith(prefix))
        .forEach((key) => {
          // Skip geo and year_range - we handle those specially
          if (
            key.startsWith('include_filters[geo]') ||
            key.startsWith('exclude_filters[geo]')
          )
            return;
          if (
            key.startsWith('include_filters[year_range]') ||
            key.startsWith('exclude_filters[year_range]')
          )
            return;

          // Match include_filters[field][] or fq[field][]
          const bracketMatch = key.match(/\[([^\]]+)\]/);
          const fieldId = bracketMatch?.[1] ?? '';
          const normalizedField = normalizeFacetId(fieldId);

          searchParamsProp.getAll(key).forEach((value) => {
            if (!value) return;
            const signature = `${type}:${normalizedField}:${value}`;
            if (seen.has(signature)) return;
            seen.add(signature);
            entries.push({
              type,
              label: getFacetLabel(normalizedField),
              value,
              fieldId: normalizedField,
            });
          });
        });
    };
    addFacetEntries('include_filters[', 'include');
    addFacetEntries('fq[', 'include');

    // 4. Year range - single entry "Year Range: start - end" (matches SearchConstraints)
    const yearStart = searchParamsProp.get(
      'include_filters[year_range][start]'
    );
    const yearEnd = searchParamsProp.get('include_filters[year_range][end]');
    if (yearStart || yearEnd) {
      entries.push({
        type: 'year_range',
        label: 'Year Range',
        value: `${yearStart || '?'} - ${yearEnd || '?'}`,
        displayValue: `${yearStart || '?'} - ${yearEnd || '?'}`,
      });
    }

    addFacetEntries('exclude_filters[', 'exclude');

    // 5. Advanced query clauses
    let globalClauseIndex = 0;
    searchParamsProp.getAll('adv_q').forEach((value) => {
      if (!value) return;
      try {
        const parsed = JSON.parse(value);
        if (Array.isArray(parsed) && parsed.length > 0) {
          parsed.forEach((clause: { op: string; f: string; q: string }) => {
            const fieldLabel = humanizeFieldName(clause.f);
            entries.push({
              type: 'advanced',
              label: `${clause.op} ${fieldLabel}`,
              value: clause.q,
              clauseIndex: globalClauseIndex,
              clauseData: clause,
            });
            globalClauseIndex++;
          });
        }
      } catch (e) {
        console.warn('Failed to parse adv_q:', e);
      }
    });

    return entries;
  }, [searchParamsProp]);

  // Match SearchConstraints badge styling
  const badgeStyles: Record<
    'query' | 'geo' | 'year_range' | 'include' | 'exclude' | 'advanced',
    string
  > = {
    query: 'bg-blue-50 text-blue-700 border border-blue-200',
    geo: 'bg-blue-50 text-blue-700 border border-blue-200',
    year_range: 'bg-blue-50 text-blue-700 border border-blue-200',
    include: 'bg-blue-50 text-blue-700 border border-blue-200',
    exclude: 'bg-red-50 text-red-700 border border-red-200',
    advanced: 'bg-purple-50 text-purple-700 border border-purple-200',
  };

  if (!isOpen) return null;

  return (
    <LightboxModal
      isOpen={isOpen}
      onClose={onClose}
      id="facet-more-modal"
      labelledBy="facet-more-modal-title"
      title={`More options for ${facetLabel}`}
      subtitle="Explore additional facet values to refine your search."
      data-testid="facet-modal-overlay"
    >
      <div className="px-6 py-3 border-b border-gray-100 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-2 w-full md:max-w-sm"
        >
          <div className="relative flex-1">
            <Search className="absolute inset-y-0 left-3 h-4 w-4 text-gray-400 my-auto" />
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search within facet values"
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
          >
            Filter
          </button>
          <button
            type="button"
            onClick={handleClearSearch}
            className="px-3 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-md hover:bg-gray-100 transition-colors"
          >
            Reset
          </button>
        </form>

        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500">Sort by</span>
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as FacetValuesSort)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {searchContextEntries.length > 0 && (
        <div className="px-6 py-2 border-b border-gray-100 bg-white">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Current search context
          </h3>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {searchContextEntries.map((entry, index) => {
              const key = `${entry.type}-${entry.label}-${entry.value}-${index}`;
              const isTogglable =
                (entry.type === 'include' || entry.type === 'exclude') &&
                Boolean(entry.fieldId);

              // Geo bbox - single consolidated badge (matches SearchConstraints)
              if (entry.type === 'geo') {
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={handleRemoveGeoFilter}
                    className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-blue-500"
                    aria-label="Remove location filter"
                  >
                    <span>
                      {entry.label}: {entry.displayValue ?? entry.value}
                    </span>
                    <X className="h-3 w-3" />
                  </button>
                );
              }

              // Year range - single consolidated badge (matches SearchConstraints)
              if (entry.type === 'year_range') {
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={handleRemoveYearRange}
                    className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-blue-500"
                    aria-label="Remove year range filter"
                  >
                    <span>
                      {entry.label}: {entry.displayValue ?? entry.value}
                    </span>
                    <X className="h-3 w-3" />
                  </button>
                );
              }

              if (isTogglable && entry.fieldId) {
                const handleClick = () => {
                  if (entry.type === 'include') {
                    onToggleFacetInclude(entry.fieldId!, entry.value);
                  } else {
                    onToggleFacetExclude(entry.fieldId!, entry.value);
                  }
                };

                const ariaLabel =
                  entry.type === 'include'
                    ? `Remove included filter ${entry.value} from ${entry.label}`
                    : `Remove excluded filter ${entry.value} from ${entry.label}`;

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={handleClick}
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 ${badgeStyles[entry.type]} ${
                      entry.type === 'include'
                        ? 'hover:bg-blue-100 focus-visible:ring-blue-500'
                        : 'hover:bg-red-100 focus-visible:ring-red-500'
                    }`}
                    aria-label={ariaLabel}
                  >
                    <span>{entry.label}:</span>
                    <span>{entry.value}</span>
                    <X className="h-3 w-3" />
                  </button>
                );
              }

              // Handle advanced clauses as removable buttons
              if (
                entry.type === 'advanced' &&
                entry.clauseIndex !== undefined
              ) {
                const handleRemoveAdvanced = () => {
                  handleRemoveAdvancedClause(entry.clauseIndex!);
                };

                const isNot = entry.clauseData?.op === 'NOT';
                const badgeStyle = isNot
                  ? 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'
                  : 'bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100';

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={handleRemoveAdvanced}
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 ${badgeStyle}`}
                    aria-label={`Remove ${entry.label}: ${entry.value}`}
                  >
                    <span>{entry.label}:</span>
                    <span>{entry.value}</span>
                    <X className="h-3 w-3" />
                  </button>
                );
              }

              return (
                <span
                  key={key}
                  className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${badgeStyles[entry.type]}`}
                >
                  <span>{entry.label}:</span>
                  <span>{entry.value}</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      <section className="relative flex-1 overflow-y-auto">
        {isInitialLoading ? (
          <div className="flex h-full items-center justify-center py-12 text-sm text-gray-500">
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Loading facet values...
          </div>
        ) : error ? (
          <div className="py-12 text-center text-sm text-red-600">{error}</div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-500">
            {emptyStateMessage}
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {items.map((item) => {
              const rawValue = item.attributes.value ?? item.id;
              const included = isValueIncluded(rawValue);
              const excluded = isValueExcluded(rawValue);
              const displayLabel = getFacetValueDisplayLabel(item, facetId);
              return (
                <li
                  key={`${facetId}-${item.id || String(rawValue)}`}
                  className="flex items-center gap-3 px-6 py-2"
                >
                  <div className="flex-1 min-w-0 flex items-center gap-2 overflow-hidden">
                    <span className="text-sm font-medium text-gray-900 truncate min-w-0">
                      {displayLabel}{' '}
                      <span className="text-gray-500 font-normal">
                        ({formatCount(item.attributes.hits)})
                      </span>
                    </span>
                    {included && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600 shrink-0">
                        <PlusCircle className="h-3 w-3" />
                        Included
                      </span>
                    )}
                    {excluded && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-600 shrink-0">
                        <MinusCircle className="h-3 w-3" />
                        Excluded
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => onToggleInclude(rawValue)}
                      className={`inline-flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium transition-colors border ${
                        included
                          ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
                          : 'text-gray-600 border-gray-200 hover:bg-gray-50'
                      }`}
                      aria-label={
                        included
                          ? `Remove ${displayLabel} from included filters`
                          : `Include ${displayLabel}`
                      }
                    >
                      <PlusCircle
                        className={`h-3 w-3 ${included ? 'text-white' : 'text-blue-500'}`}
                      />
                      {included ? 'Included' : 'Include'}
                    </button>
                    <button
                      onClick={() => onToggleExclude(rawValue)}
                      className={`inline-flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium transition-colors border ${
                        excluded
                          ? 'border-rose-400 text-rose-600 bg-rose-50 hover:bg-rose-100'
                          : 'text-gray-600 border-gray-200 hover:bg-gray-50'
                      }`}
                      aria-label={
                        excluded
                          ? `Remove ${displayLabel} from excluded filters`
                          : `Exclude ${displayLabel}`
                      }
                    >
                      <MinusCircle
                        className={`h-3 w-3 ${excluded ? 'text-rose-500' : 'text-rose-400'}`}
                      />
                      {excluded ? 'Excluded' : 'Exclude'}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {isRefetching && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Loader2 className="h-4 w-4 animate-spin" />
              Updating facet values…
            </div>
          </div>
        )}
      </section>

      <footer className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="text-sm text-gray-600">
          Showing page {page} of {totalPages} • {formatCount(totalCount)} total
          values
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page <= 1 || isLoading}
            className="flex items-center gap-1 px-3 py-2 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages || isLoading}
            className="flex items-center gap-1 px-3 py-2 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 transition-colors"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </footer>
    </LightboxModal>
  );
}
