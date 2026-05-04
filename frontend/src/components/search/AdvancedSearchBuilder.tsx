import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { Plus, X, Sparkles } from 'lucide-react';
import { useSearchParams } from 'react-router';
import type { AdvancedClause, AdvancedOperator } from '../../types/search';
import {
  FIELD_LABELS,
  isFieldFacetable,
  getFacetNameForField,
} from '../../constants/fieldLabels';
import { fetchFacetValues } from '../../services/api';
import type { FacetValue } from '../../types/api';
import { getFacetValueDisplayLabel } from '../../utils/facetDisplay';
import { formatCount } from '../../utils/formatNumber';
import { debugLog } from '../../utils/logger';

interface AdvancedSearchBuilderProps {
  clauses: AdvancedClause[];
  onApply: (clauses: AdvancedClause[]) => void;
  onCancel: () => void;
  onReset: () => void;
}

type BuilderRow = AdvancedClause & { id: string };

const OPERATORS: AdvancedOperator[] = ['AND', 'OR', 'NOT'];

const ADVANCED_SEARCH_FIELD_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'all_fields', label: 'All Fields' },
  { value: 'dct_title_s', label: 'Title' },
  { value: 'dct_accessRights_s', label: 'Access Rights' },
  { value: 'dct_creator_sm', label: 'Creator' },
  { value: 'dct_description_sm', label: 'Description' },
  { value: 'b1g_localCollectionLabel_sm', label: 'Local Collection' },
  { value: 'dct_spatial_sm', label: 'Place' },
  { value: 'schema_provider_s', label: 'Provider' },
  { value: 'dct_publisher_sm', label: 'Publisher' },
  { value: 'gbl_resourceClass_sm', label: 'Resource Class' },
  { value: 'gbl_resourceType_sm', label: 'Resource Type' },
  { value: 'dct_subject_sm', label: 'Subject' },
  { value: 'dcat_theme_sm', label: 'Theme' },
];

const DEFAULT_FIELD = ADVANCED_SEARCH_FIELD_OPTIONS[0]?.value || 'dct_title_s';

const generateRowId = () => {
  const globalCrypto =
    typeof globalThis !== 'undefined'
      ? (globalThis.crypto as Crypto | undefined)
      : undefined;
  if (globalCrypto?.randomUUID) {
    return globalCrypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
};

function createRow(partial?: Partial<AdvancedClause>): BuilderRow {
  return {
    id: generateRowId(),
    op: partial?.op || 'AND',
    field: partial?.field || DEFAULT_FIELD,
    q: partial?.q || '',
  };
}

interface AutocompleteState {
  rowId: string;
  suggestions: FacetValue[];
  isLoading: boolean;
  isOpen: boolean;
  selectedIndex: number;
}

export function AdvancedSearchBuilder({
  clauses,
  onApply,
  onCancel,
  onReset,
}: AdvancedSearchBuilderProps) {
  // Note: searchParams is available but not currently used in this component
  // Keeping useSearchParams call for potential future use
  useSearchParams();
  const [rows, setRows] = useState<BuilderRow[]>(() =>
    clauses.length > 0
      ? clauses.map((clause) => createRow(clause))
      : [createRow()]
  );
  const [error, setError] = useState<string | null>(null);
  const [autocomplete, setAutocomplete] = useState<AutocompleteState | null>(
    null
  );
  const autocompleteTimeoutRef = useRef<Record<string, NodeJS.Timeout>>({});
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const fieldSelectRefs = useRef<Record<string, HTMLSelectElement | null>>({});
  const suggestionsRef = useRef<HTMLDivElement | null>(null);
  const hasFocusedInitial = useRef(false);
  const focusAttemptRef = useRef(0);

  useEffect(() => {
    setRows(
      clauses.length > 0
        ? clauses.map((clause) => createRow(clause))
        : [createRow()]
    );
    // Reset focus flag when component mounts/remounts
    hasFocusedInitial.current = false;
    focusAttemptRef.current = 0;
  }, [clauses]);

  // Focus the first field select when component mounts or becomes visible
  useEffect(() => {
    if (hasFocusedInitial.current) return;

    const attemptFocus = () => {
      const firstRowId = rows[0]?.id;
      if (firstRowId && fieldSelectRefs.current[firstRowId]) {
        const selectElement = fieldSelectRefs.current[firstRowId];
        if (selectElement && selectElement.offsetParent !== null) {
          // Element is visible and in the DOM.
          // Use preventScroll: true so focus does not scroll the page when the user
          // has already scrolled down to view results (avoids jumping back to form).
          selectElement.focus({ preventScroll: true });
          hasFocusedInitial.current = true;
          return true;
        }
      }
      return false;
    };

    // Use multiple attempts with increasing delays to ensure it works
    // This handles cases where the component is conditionally rendered
    const timeouts: NodeJS.Timeout[] = [];

    // First attempt: after current event loop completes
    timeouts.push(
      setTimeout(() => {
        if (!hasFocusedInitial.current && !attemptFocus()) {
          // Second attempt: after a short delay
          timeouts.push(
            setTimeout(() => {
              if (!hasFocusedInitial.current && !attemptFocus()) {
                // Third attempt: after a longer delay
                timeouts.push(
                  setTimeout(() => {
                    if (!hasFocusedInitial.current) {
                      attemptFocus();
                    }
                  }, 150)
                );
              }
            }, 100)
          );
        }
      }, 0)
    );

    return () => {
      timeouts.forEach(clearTimeout);
    };
  }, [rows]); // Run when rows change (including initial mount)

  // Cleanup timeouts on unmount
  useEffect(() => {
    const timeoutRef = autocompleteTimeoutRef;
    return () => {
      Object.values(timeoutRef.current).forEach((timeout) => {
        clearTimeout(timeout);
      });
    };
  }, []);

  // Close autocomplete when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node) &&
        !Object.values(inputRefs.current).some((ref) =>
          ref?.contains(event.target as Node)
        )
      ) {
        setAutocomplete((prev) => (prev ? { ...prev, isOpen: false } : null));
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Build search context from current form rows (excluding the row being edited)
  const buildSearchContext = useCallback(
    (excludeRowId: string): URLSearchParams => {
      const contextParams = new URLSearchParams();

      // Get all rows except the one being edited
      const contextRows = rows.filter(
        (row) => row.id !== excludeRowId && row.q.trim().length > 0
      );

      if (contextRows.length === 0) {
        // No context rows, return empty params (will search all)
        return contextParams;
      }

      // Check if there's a basic query (all_fields)
      const basicQueryRow = contextRows.find(
        (row) => row.field === 'all_fields'
      );
      if (basicQueryRow) {
        contextParams.set('q', basicQueryRow.q.trim());
      }

      // Build advanced query from non-basic rows
      const advancedRows = contextRows.filter(
        (row) => row.field !== 'all_fields'
      );
      if (advancedRows.length > 0) {
        const serialized = advancedRows.map(({ op, field, q }) => ({
          op,
          f: field,
          q: q.trim(),
        }));
        contextParams.set('adv_q', JSON.stringify(serialized));
      }

      return contextParams;
    },
    [rows]
  );

  const fetchFacetSuggestions = useCallback(
    async (rowId: string, fieldName: string, query: string) => {
      const facetName = getFacetNameForField(fieldName);
      if (!facetName) return;

      setAutocomplete((prev) =>
        prev?.rowId === rowId
          ? { ...prev, isLoading: true, isOpen: true }
          : {
              rowId,
              suggestions: [],
              isLoading: true,
              isOpen: true,
              selectedIndex: -1,
            }
      );

      try {
        // Build search context from current form rows (excluding the row being edited)
        const contextParams = buildSearchContext(rowId);

        debugLog('Fetching facet suggestions for:', {
          fieldName,
          facetName,
          query,
          context: Object.fromEntries(contextParams.entries()),
        });

        const response = await fetchFacetValues({
          facetName,
          searchParams: contextParams,
          perPage: 20,
          qFacet: query || undefined,
          sort: 'count_desc',
        });

        debugLog('Facet suggestions response:', {
          fieldName,
          facetName,
          count: response.data?.length || 0,
          data: response.data,
        });

        setAutocomplete((prev) =>
          prev?.rowId === rowId
            ? {
                ...prev,
                suggestions: response.data || [],
                isLoading: false,
                selectedIndex: -1,
              }
            : prev
        );
      } catch (err) {
        console.error('Error fetching facet suggestions:', {
          fieldName,
          facetName,
          error: err,
        });
        setAutocomplete((prev) =>
          prev?.rowId === rowId
            ? {
                ...prev,
                suggestions: [],
                isLoading: false,
              }
            : prev
        );
      }
    },
    [buildSearchContext]
  );

  const handleFieldChange = (rowId: string, fieldName: string) => {
    // Clear any pending timeouts for this row
    if (autocompleteTimeoutRef.current[rowId]) {
      clearTimeout(autocompleteTimeoutRef.current[rowId]);
      delete autocompleteTimeoutRef.current[rowId];
    }

    // Always close/reset autocomplete when field changes
    setAutocomplete((prev) => (prev?.rowId === rowId ? null : prev));

    updateRow(rowId, 'field', fieldName);
    // Clear the value when field changes
    updateRow(rowId, 'q', '');
  };

  const handleValueChange = (rowId: string, value: string) => {
    updateRow(rowId, 'q', value);
    const row = rows.find((r) => r.id === rowId);

    // If this row has autocomplete open, refetch its suggestions
    if (row && isFieldFacetable(row.field)) {
      // Clear existing timeout
      if (autocompleteTimeoutRef.current[rowId]) {
        clearTimeout(autocompleteTimeoutRef.current[rowId]);
      }

      // Debounce facet fetching for this row
      // Note: fetchFacetSuggestions will use buildSearchContext which reads from rows state
      // By the time the timeout fires, the state will be updated
      autocompleteTimeoutRef.current[rowId] = setTimeout(() => {
        // Use the value parameter directly, but get field from updated state
        // We'll use a ref to get the latest rows, or just rely on the closure
        // Since buildSearchContext uses rows from closure, we need to ensure it has latest
        // Actually, buildSearchContext is a useCallback with rows dependency, so it will have latest
        fetchFacetSuggestions(rowId, row.field, value);
      }, 300);
    }

    // If another row has autocomplete open, refetch its suggestions
    // (because the context has changed)
    if (autocomplete && autocomplete.rowId !== rowId && autocomplete.isOpen) {
      const otherRow = rows.find((r) => r.id === autocomplete.rowId);
      if (otherRow && isFieldFacetable(otherRow.field)) {
        // Clear existing timeout for the other row
        if (autocompleteTimeoutRef.current[autocomplete.rowId]) {
          clearTimeout(autocompleteTimeoutRef.current[autocomplete.rowId]);
        }
        // Refetch with updated context
        // buildSearchContext will use the updated rows state (excluding the changed rowId)
        autocompleteTimeoutRef.current[autocomplete.rowId] = setTimeout(() => {
          fetchFacetSuggestions(autocomplete.rowId, otherRow.field, otherRow.q);
        }, 300);
      }
    }
  };

  const handleValueFocus = (rowId: string) => {
    const row = rows.find((r) => r.id === rowId);
    if (!row || !isFieldFacetable(row.field)) return;

    // Fetch initial suggestions if autocomplete is not already open
    if (!autocomplete || autocomplete.rowId !== rowId || !autocomplete.isOpen) {
      fetchFacetSuggestions(rowId, row.field, row.q);
    }
  };

  const handleValueBlur = (rowId: string) => {
    // Use a small delay to allow clicking on suggestions before closing
    setTimeout(() => {
      setAutocomplete((prev) => {
        // Only close if the blur is for the current autocomplete row
        // and the click wasn't on a suggestion
        if (prev?.rowId === rowId) {
          const activeElement = document.activeElement;
          const suggestionsElement = suggestionsRef.current;
          // If focus moved to a suggestion, don't close
          if (suggestionsElement?.contains(activeElement)) {
            return prev;
          }
          return null;
        }
        return prev;
      });
    }, 200);
  };

  const handleSuggestionSelect = (rowId: string, value: string) => {
    updateRow(rowId, 'q', value);
    setAutocomplete((prev) =>
      prev?.rowId === rowId ? { ...prev, isOpen: false } : prev
    );
  };

  const handleKeyDown = (
    rowId: string,
    event: React.KeyboardEvent<HTMLInputElement>
  ) => {
    if (!autocomplete || autocomplete.rowId !== rowId || !autocomplete.isOpen)
      return;

    const { selectedIndex, suggestions } = autocomplete;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setAutocomplete((prev) =>
        prev?.rowId === rowId
          ? {
              ...prev,
              selectedIndex: Math.min(
                selectedIndex + 1,
                suggestions.length - 1
              ),
            }
          : prev
      );
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setAutocomplete((prev) =>
        prev?.rowId === rowId
          ? {
              ...prev,
              selectedIndex: Math.max(selectedIndex - 1, -1),
            }
          : prev
      );
    } else if (
      event.key === 'Enter' &&
      selectedIndex >= 0 &&
      suggestions[selectedIndex]
    ) {
      event.preventDefault();
      const selected = suggestions[selectedIndex];
      const value = String(selected.attributes.value);
      handleSuggestionSelect(rowId, value);
    } else if (event.key === 'Escape') {
      setAutocomplete((prev) =>
        prev?.rowId === rowId ? { ...prev, isOpen: false } : prev
      );
    }
  };

  const fieldOptions = useMemo(() => {
    const seen = new Set(
      ADVANCED_SEARCH_FIELD_OPTIONS.map((option) => option.value)
    );
    const legacySelections = Array.from(new Set(rows.map((row) => row.field)))
      .filter((field) => !seen.has(field))
      .map((field) => ({
        value: field,
        label:
          field === 'all_fields'
            ? 'All Text'
            : FIELD_LABELS[field]?.label || field,
      }));

    // Preserve any existing field selections from older URLs so they still render/edit cleanly.
    return [...ADVANCED_SEARCH_FIELD_OPTIONS, ...legacySelections];
  }, [rows]);

  const updateRow = (id: string, key: keyof AdvancedClause, value: string) => {
    setRows((prev) =>
      prev.map((row) => (row.id === id ? { ...row, [key]: value } : row))
    );
  };

  const removeRow = (id: string) => {
    // Cleanup autocomplete and timeout for removed row
    if (autocompleteTimeoutRef.current[id]) {
      clearTimeout(autocompleteTimeoutRef.current[id]);
      delete autocompleteTimeoutRef.current[id];
    }
    setAutocomplete((prev) => (prev?.rowId === id ? null : prev));
    delete inputRefs.current[id];
    delete fieldSelectRefs.current[id];
    setRows((prev) =>
      prev.length === 1 ? prev : prev.filter((row) => row.id !== id)
    );
  };

  const handleAddRow = () => {
    const newRow = createRow();
    setRows((prev) => [...prev, newRow]);
    // Focus the newly added field select after it's rendered
    setTimeout(() => {
      if (fieldSelectRefs.current[newRow.id]) {
        fieldSelectRefs.current[newRow.id]?.focus();
      }
    }, 0);
  };

  const handleApply = () => {
    const sanitized = rows
      .map(({ op, field, q }) => ({
        op,
        field,
        q: q.trim(),
      }))
      .filter((row) => row.q.length > 0);

    setError(null);
    onApply(sanitized);
  };

  const handleReset = () => {
    setRows([createRow()]);
    setError(null);
    onReset();
  };

  return (
    <div className="bg-white border border-blue-200 rounded-lg shadow-sm p-4 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-blue-800">
            Advanced Search Builder
          </h3>
          <p className="text-sm text-blue-600">
            Combine multiple fields and boolean operators to refine your
            results.
          </p>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 transition-colors"
          aria-label="Close advanced search builder"
        >
          <X className="h-4 w-4" />
          Close
        </button>
      </div>

      <div className="space-y-3">
        {rows.map((row, index) => (
          <div
            key={row.id}
            className="flex flex-col gap-3 md:grid md:grid-cols-12 md:items-center md:gap-4"
          >
            <label className="flex flex-col gap-1 md:col-span-4">
              <span className="text-xs font-semibold text-blue-700 uppercase">
                Field
              </span>
              <select
                ref={(el) => {
                  fieldSelectRefs.current[row.id] = el;
                  // Focus the first field select when it's mounted (first row, first render)
                  if (index === 0 && el && !hasFocusedInitial.current) {
                    // Try to focus immediately
                    if (el.offsetParent !== null) {
                      // Element is visible, focus it
                      requestAnimationFrame(() => {
                        el.focus();
                        hasFocusedInitial.current = true;
                      });
                    } else {
                      // Element not yet visible, wait a bit
                      setTimeout(() => {
                        if (
                          el.offsetParent !== null &&
                          !hasFocusedInitial.current
                        ) {
                          el.focus();
                          hasFocusedInitial.current = true;
                        }
                      }, 100);
                    }
                  }
                }}
                value={row.field}
                onChange={(event) =>
                  handleFieldChange(row.id, event.target.value)
                }
                className="rounded-md border border-blue-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {fieldOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 md:col-span-5 relative">
              <span className="text-xs font-semibold text-blue-700 uppercase flex items-center gap-1">
                Value
                {isFieldFacetable(row.field) && (
                  <Sparkles
                    className="h-3 w-3 text-blue-500"
                    aria-label="Autocomplete available"
                  />
                )}
              </span>
              <div className="relative">
                <input
                  ref={(el) => {
                    inputRefs.current[row.id] = el;
                  }}
                  type="text"
                  value={row.q}
                  onChange={(event) =>
                    handleValueChange(row.id, event.target.value)
                  }
                  onFocus={() => handleValueFocus(row.id)}
                  onBlur={() => handleValueBlur(row.id)}
                  onKeyDown={(event) => handleKeyDown(row.id, event)}
                  className="rounded-md border border-blue-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 w-full"
                  placeholder={
                    isFieldFacetable(row.field)
                      ? 'Type to search or select from suggestions'
                      : 'Enter search term'
                  }
                />
                {autocomplete?.rowId === row.id &&
                  isFieldFacetable(row.field) &&
                  autocomplete.isOpen && (
                    <div
                      ref={suggestionsRef}
                      className="absolute z-10 w-full mt-1 bg-white rounded-lg shadow-lg border border-blue-200 max-h-60 overflow-auto"
                    >
                      {autocomplete.isLoading ? (
                        <div className="px-4 py-2 text-sm text-gray-500">
                          Loading suggestions...
                        </div>
                      ) : autocomplete.suggestions.length === 0 ? (
                        <div className="px-4 py-2 text-sm text-gray-500">
                          No suggestions found
                        </div>
                      ) : (
                        autocomplete.suggestions.map((suggestion, index) => {
                          const rawValue =
                            suggestion.attributes.value ?? suggestion.id;
                          const value = String(rawValue);
                          const displayLabel =
                            getFacetValueDisplayLabel(suggestion);
                          const hits = suggestion.attributes.hits;
                          const isSelected =
                            index === autocomplete.selectedIndex;

                          return (
                            <button
                              key={suggestion.id || index}
                              type="button"
                              onClick={() =>
                                handleSuggestionSelect(row.id, value)
                              }
                              className={`w-full text-left px-4 py-2 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none transition-colors ${
                                isSelected ? 'bg-blue-50' : ''
                              }`}
                              onMouseEnter={() =>
                                setAutocomplete((prev) =>
                                  prev?.rowId === row.id
                                    ? { ...prev, selectedIndex: index }
                                    : prev
                                )
                              }
                            >
                              <div className="text-sm text-gray-900">
                                {displayLabel}
                              </div>
                              {hits !== undefined && (
                                <div className="text-xs text-gray-500">
                                  {formatCount(hits)}{' '}
                                  {hits === 1 ? 'result' : 'results'}
                                </div>
                              )}
                            </button>
                          );
                        })
                      )}
                    </div>
                  )}
              </div>
            </label>

            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-xs font-semibold text-blue-700 uppercase">
                Operator
              </span>
              <select
                value={row.op}
                onChange={(event) =>
                  updateRow(row.id, 'op', event.target.value)
                }
                className="rounded-md border border-blue-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {OPERATORS.map((operator) => (
                  <option key={operator} value={operator}>
                    {operator}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex justify-end md:col-span-1">
              <button
                type="button"
                onClick={() => removeRow(row.id)}
                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 transition-colors disabled:text-blue-300"
                disabled={rows.length === 1}
                aria-label={
                  rows.length === 1
                    ? 'Cannot remove the last row'
                    : 'Remove condition'
                }
              >
                <X className="h-4 w-4" />
                {index === 0 ? 'Clear' : 'Remove'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <button
          type="button"
          onClick={handleAddRow}
          className="inline-flex items-center justify-center gap-2 rounded-md border border-dashed border-blue-300 px-4 py-2 text-sm font-medium text-blue-700 hover:border-blue-400 hover:text-blue-900 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Condition
        </button>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReset}
            className="rounded-md border border-blue-300 px-4 py-2 text-sm font-medium text-blue-700 hover:border-blue-400 hover:text-blue-900 transition-colors"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={handleApply}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
