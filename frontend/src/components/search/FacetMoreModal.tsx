import { FormEvent, useEffect, useMemo, useState, MouseEvent } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  MinusCircle,
  PlusCircle,
  Search,
  X,
} from 'lucide-react';
import { useSearchParams } from 'react-router';
import { useFacetModal } from '../../hooks/useFacetModal';
import type { FacetValuesSort } from '../../types/api';
import { FACET_LABELS, normalizeFacetId } from '../../utils/facetLabels';
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

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

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

  const handleOverlayMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  const emptyStateMessage = useMemo(() => {
    if (isLoading) return 'Loading facet values...';
    if (qFacet) return 'No facet values match your filter.';
    return 'No facet values available.';
  }, [isLoading, qFacet]);

  const searchContextEntries = useMemo(() => {
    const entries: Array<{
      type: 'query' | 'include' | 'exclude' | 'advanced';
      label: string;
      value: string;
      fieldId?: string;
      clauseIndex?: number; // For advanced clauses: index within the adv_q array
      clauseData?: { op: string; f: string; q: string }; // For advanced clauses: the clause data
    }> = [];
    const seen = new Set<string>();

    const queryValue = searchParamsProp.get('q');
    if (queryValue) {
      entries.push({
        type: 'query',
        label: 'Search',
        value: queryValue,
      });
    }

    // Parse and create individual entries for each advanced query clause
    // Note: There should only be one adv_q param, but we handle multiple for safety
    let globalClauseIndex = 0;
    searchParamsProp.getAll('adv_q').forEach((value) => {
      if (!value) return;
      try {
        const parsed = JSON.parse(value);
        if (Array.isArray(parsed) && parsed.length > 0) {
          // Create a separate entry for each clause
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
        // If parsing fails, skip this adv_q entry
        console.warn('Failed to parse adv_q:', e);
      }
    });

    const addFacetEntries = (
      prefix: 'include_filters[' | 'exclude_filters[' | 'fq[',
      type: 'include' | 'exclude'
    ) => {
      Array.from(searchParamsProp.keys())
        .filter((key) => key.startsWith(prefix))
        .forEach((key) => {
          const fieldMatch = key.match(/\[(.*?)\]/);
          const fieldId = fieldMatch?.[1] ?? '';
          const normalizedField = normalizeFacetId(fieldId);
          const displayLabel =
            FACET_LABELS[normalizedField] ||
            FACET_LABELS[fieldId] ||
            fieldId ||
            'Facet';

          searchParamsProp.getAll(key).forEach((value) => {
            if (!value) return;
            const signature = `${type}:${normalizedField}:${value}`;
            if (seen.has(signature)) return;
            seen.add(signature);
            entries.push({
              type,
              label: displayLabel,
              value,
              fieldId,
            });
          });
        });
    };

    addFacetEntries('include_filters[', 'include');
    addFacetEntries('fq[', 'include');
    addFacetEntries('exclude_filters[', 'exclude');

    return entries;
  }, [searchParamsProp]);

  const badgeStyles: Record<
    'query' | 'include' | 'exclude' | 'advanced',
    string
  > = {
    query: 'bg-blue-50 text-blue-700 border border-blue-200',
    include: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    exclude: 'bg-rose-50 text-rose-700 border border-rose-200',
    advanced: 'bg-indigo-50 text-indigo-700 border border-indigo-200',
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[10000] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
      onMouseDown={handleOverlayMouseDown}
      data-testid="facet-modal-overlay"
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              More options for {facetLabel}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Explore additional facet values to refine your search.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close facet modal"
          >
            <X className="h-6 w-6" />
          </button>
        </header>

        <div className="px-6 py-4 border-b border-gray-100 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
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
              onChange={(event) =>
                setSort(event.target.value as FacetValuesSort)
              }
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
          <div className="px-6 py-3 border-b border-gray-100 bg-white">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Current search context
            </h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {searchContextEntries.map((entry, index) => {
                const key = `${entry.type}-${entry.label}-${entry.value}-${index}`;
                const isTogglable =
                  (entry.type === 'include' || entry.type === 'exclude') &&
                  Boolean(entry.fieldId);

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
                          ? 'hover:bg-emerald-100 focus-visible:ring-emerald-500'
                          : 'hover:bg-rose-100 focus-visible:ring-rose-500'
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
            <div className="py-12 text-center text-sm text-red-600">
              {error}
            </div>
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
                const displayLabel = getFacetValueDisplayLabel(item);
                return (
                  <li
                    key={`${facetId}-${item.id || String(rawValue)}`}
                    className="flex items-center justify-between px-6 py-3 gap-4"
                  >
                    <div className="flex-1">
                      <div className="text-sm font-medium text-gray-900">
                        {displayLabel}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        ({formatCount(item.attributes.hits)})
                      </div>
                      <div className="mt-2 flex items-center gap-2 text-xs">
                        {included && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-blue-600">
                            <PlusCircle className="h-3 w-3" />
                            Included
                          </span>
                        )}
                        {excluded && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-rose-600">
                            <MinusCircle className="h-3 w-3" />
                            Excluded
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onToggleInclude(rawValue)}
                        className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors border ${
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
                          className={`h-4 w-4 ${included ? 'text-white' : 'text-blue-500'}`}
                        />
                        {included ? 'Included' : 'Include'}
                      </button>
                      <button
                        onClick={() => onToggleExclude(rawValue)}
                        className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors border ${
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
                          className={`h-4 w-4 ${excluded ? 'text-rose-500' : 'text-rose-400'}`}
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
            Showing page {page} of {totalPages} • {formatCount(totalCount)} total values
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
      </div>
    </div>
  );
}
