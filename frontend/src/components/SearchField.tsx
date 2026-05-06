import React, { useState, useEffect, useRef } from 'react';
import { Search, Settings, X, MapPin } from 'lucide-react';
import { fetchNominatimSearch } from '../services/api';
import { useNavigate, useSearchParams } from 'react-router';
import type { GazetteerPlace } from '../types/api';

function useMediaQuery(query: string): boolean {
  // SSR-safe: during the initial server render and the initial client hydration
  // we must return the same value, otherwise React will warn about mismatched
  // `className`/markup. We'll compute the real value after mount.
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    const m = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    m.addEventListener('change', handler);
    setMatches(m.matches);
    return () => m.removeEventListener('change', handler);
  }, [query]);
  return matches;
}

interface SearchFieldProps {
  onSearch?: (query: string) => void;
  placeholder?: string;
  initialQuery?: string;
  autoFocus?: boolean;
  showAdvancedButton?: boolean;
  onAdvancedSearchClick?: () => void;
}

interface GeoBBoxParams {
  topLeftLat: string;
  topLeftLon: string;
  bottomRightLat: string;
  bottomRightLon: string;
}

type SearchSuggestion = { text: string };
type SearchSuggestionResponseItem = {
  attributes?: {
    text?: string;
  };
};

type ScopeSuggestion = {
  kind: 'scope';
  id: string;
  searchField: 'dct_title_s' | 'dct_subject_sm,dcat_theme_sm';
  label: string;
};

type KeywordSuggestionItem =
  | ScopeSuggestion
  | { kind: 'place'; id: string; place: GazetteerPlace }
  | { kind: 'place_loading'; id: string }
  | { kind: 'suggestion'; id: string; suggestion: SearchSuggestion }
  | { kind: 'see_all'; id: string };

type KeywordSuggestionGroup = 'scope' | 'place' | 'suggestion' | 'see_all';

const NOMINATIM_SUGGESTION_LIMIT = 5;

const PLACE_TYPE_LABELS: Record<string, string> = {
  city: 'City',
  town: 'Town',
  village: 'Village',
  hamlet: 'Hamlet',
  municipality: 'Municipality',
  county: 'County',
  state: 'State',
  region: 'Region',
  province: 'Province',
  country: 'Country',
  administrative: 'Administrative Area',
};

const SCOPED_SEARCH_OPTIONS: ScopeSuggestion[] = [
  {
    kind: 'scope',
    id: 'scope-title',
    searchField: 'dct_title_s',
    label: 'Title',
  },
  {
    kind: 'scope',
    id: 'scope-subject-theme',
    searchField: 'dct_subject_sm,dcat_theme_sm',
    label: 'Subject/Theme',
  },
];

function setGeoBBoxParams(
  params: URLSearchParams,
  bbox: GeoBBoxParams,
  relation: 'within' | 'intersects' = 'intersects'
) {
  params.set('include_filters[geo][type]', 'bbox');
  params.set('include_filters[geo][field]', 'dcat_bbox');
  params.set('include_filters[geo][relation]', relation);
  params.set('include_filters[geo][top_left][lat]', bbox.topLeftLat);
  params.set('include_filters[geo][top_left][lon]', bbox.topLeftLon);
  params.set('include_filters[geo][bottom_right][lat]', bbox.bottomRightLat);
  params.set('include_filters[geo][bottom_right][lon]', bbox.bottomRightLon);
}

function formatPlaceTypeLabel(placeType: string | null | undefined) {
  const normalized = (placeType || '').trim().replace(/_/g, ' ').toLowerCase();
  if (!normalized) return null;
  return (
    PLACE_TYPE_LABELS[normalized] ||
    normalized.replace(/\b\w/g, (char) => char.toUpperCase())
  );
}

export function SearchField({
  onSearch: _onSearch, // eslint-disable-line @typescript-eslint/no-unused-vars
  placeholder = 'Search...',
  initialQuery = '',
  autoFocus,
  showAdvancedButton = false,
  onAdvancedSearchClick,
}: SearchFieldProps) {
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Placename autocomplete state
  const [selectedPlace, setSelectedPlace] = useState<GazetteerPlace | null>(
    null
  );
  const [placeSuggestions, setPlaceSuggestions] = useState<GazetteerPlace[]>(
    []
  );
  const [isLoadingPlaces, setIsLoadingPlaces] = useState(false);
  const [isKeywordInputFocused, setIsKeywordInputFocused] = useState(false);

  const isXlOrLarger = useMediaQuery('(min-width: 1280px)');

  // Full placeholder at xl+ (1280px); short "Search…" below. Guard: if placeholder was customized (not default), prefer full at lg+.
  const fullPlaceholderPreferred = placeholder !== 'Search...' || isXlOrLarger;
  const responsivePlaceholder = fullPlaceholderPreferred
    ? placeholder
    : 'Search…';

  const getGeoRelationFromParams = () => {
    const relation = searchParams.get('include_filters[geo][relation]');
    return relation === 'within' ? 'within' : 'intersects';
  };

  const getActiveSearchField = () =>
    searchParams.get('search_field') || 'all_fields';

  // Sync query with URL params (e.g., when Clear All sets q to empty)
  useEffect(() => {
    const urlQuery = searchParams.has('q')
      ? searchParams.get('q') || ''
      : initialQuery;
    // Only update if the URL value is different from current state
    // This handles cases where the URL changes outside this field.
    // Note: We don't include 'query' in deps to avoid resetting while user types
    if (urlQuery !== query) {
      setQuery(urlQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery, searchParams]); // Watch for URL param changes only

  // Sync place selection with URL params (clear if geo filters removed)
  useEffect(() => {
    const type = searchParams.get('include_filters[geo][type]');
    if (type !== 'bbox' && selectedPlace) {
      // Geo filters were removed, clear the place
      setSelectedPlace(null);
    }
  }, [searchParams, selectedPlace]);

  // Fetch keyword suggestions
  useEffect(() => {
    let isCurrent = true;
    if (!query.trim()) {
      setSuggestions([]);
      return () => {
        isCurrent = false;
      };
    }
    if (!isKeywordInputFocused) {
      return () => {
        isCurrent = false;
      };
    }

    const fetchSuggestionsDebounced = setTimeout(async () => {
      try {
        // IMPORTANT: Do not call the API directly from the browser when rate limiting is enabled.
        // `/suggest` is served by the SSR server, which injects the API key server-side.
        const res = await fetch(
          `/suggest?q=${encodeURIComponent(query.trim())}`,
          {
            headers: { Accept: 'application/json' },
          }
        );
        const json = await res.json();
        const data: SearchSuggestionResponseItem[] = Array.isArray(json?.data)
          ? json.data
          : [];
        if (!isCurrent) return;
        setSuggestions(
          data
            .map((r) => ({
              text: r.attributes?.text ?? '',
            }))
            .filter((suggestion) => suggestion.text)
        );
      } catch (error) {
        console.error('Error fetching keyword suggestions:', error);
        if (isCurrent) {
          setSuggestions([]);
        }
      }
    }, 300);

    return () => {
      isCurrent = false;
      clearTimeout(fetchSuggestionsDebounced);
    };
  }, [query, isKeywordInputFocused]);

  // Fetch placename suggestions
  useEffect(() => {
    let isCurrent = true;
    if (!query.trim()) {
      setPlaceSuggestions([]);
      setIsLoadingPlaces(false);
      return () => {
        isCurrent = false;
      };
    }
    if (!isKeywordInputFocused) {
      setIsLoadingPlaces(false);
      return () => {
        isCurrent = false;
      };
    }

    const fetchPlaceSuggestionsDebounced = setTimeout(async () => {
      setIsLoadingPlaces(true);
      try {
        const response = await fetchNominatimSearch(
          query.trim(),
          NOMINATIM_SUGGESTION_LIMIT
        );
        if (!isCurrent) return;
        setPlaceSuggestions(
          (response.data || []).slice(0, NOMINATIM_SUGGESTION_LIMIT)
        );
      } catch (error) {
        console.error('Error fetching placename suggestions:', error);
        if (isCurrent) {
          setPlaceSuggestions([]);
        }
      } finally {
        if (isCurrent) {
          setIsLoadingPlaces(false);
        }
      }
    }, 500); // Longer debounce for Nominatim rate limiting

    return () => {
      isCurrent = false;
      clearTimeout(fetchPlaceSuggestionsDebounced);
    };
  }, [query, isKeywordInputFocused]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const clickedKeywordField =
        suggestionsRef.current?.contains(target) ||
        inputRef.current?.contains(target);

      if (!clickedKeywordField) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectPlace = (place: GazetteerPlace) => {
    const attrs = place.attributes;

    setSelectedPlace(place);
    setSuggestions([]);
    setPlaceSuggestions([]);
    setShowSuggestions(false);
    setSelectedIndex(-1);

    // Create bbox from min/max lat/lng
    const newParams = new URLSearchParams(searchParams);

    newParams.set('q', '');
    newParams.delete('search_field');
    setQuery('');

    // Remove existing geo filters
    Array.from(newParams.keys())
      .filter((key) => key.startsWith('include_filters[geo]'))
      .forEach((key) => newParams.delete(key));

    // Add new bbox filter
    // top_left is northwest (higher lat, lower lon)
    // bottom_right is southeast (lower lat, higher lon)
    const topLeftLat = attrs.max_latitude;
    const topLeftLon = attrs.min_longitude;
    const bottomRightLat = attrs.min_latitude;
    const bottomRightLon = attrs.max_longitude;

    setGeoBBoxParams(newParams, {
      topLeftLat: topLeftLat.toString(),
      topLeftLon: topLeftLon.toString(),
      bottomRightLat: bottomRightLat.toString(),
      bottomRightLon: bottomRightLon.toString(),
    });

    // Other filters (e.g. category) are already in newParams from the copy above; do not re-append or we duplicate.

    // Reset to page 1 when bbox changes
    newParams.delete('page');

    navigate(`/search?${newParams.toString()}`);
  };

  const handleClearPlace = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedPlace(null);
    setPlaceSuggestions([]);

    // Remove geo filters but preserve keyword query and other filters
    const newParams = new URLSearchParams(searchParams);

    // Preserve keyword query
    const currentQuery = query.trim() || searchParams.get('q') || '';
    if (currentQuery) {
      newParams.set('q', currentQuery);
    }

    // Remove geo filters
    Array.from(newParams.keys())
      .filter((key) => key.startsWith('include_filters[geo]'))
      .forEach((key) => newParams.delete(key));

    newParams.delete('page');

    // Navigate to update URL
    navigate(`/search?${newParams.toString()}`);
  };

  const handleClearSearchField = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const newParams = new URLSearchParams(searchParams);
    const currentQuery = query.trim() || searchParams.get('q') || '';
    newParams.set('q', currentQuery);
    newParams.delete('search_field');
    newParams.delete('page');

    navigate(`/search?${newParams.toString()}`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newParams = buildSearchNavigationParams(query.trim());
    navigate(`/search?${newParams.toString()}`);
    setShowSuggestions(false);
  };

  const buildSearchNavigationParams = (
    nextQuery: string,
    options?: { searchField?: string }
  ) => {
    const newParams = new URLSearchParams();

    // Always set q so the search page runs (useSearch requires hasQueryParam = searchParams.has('q'))
    newParams.set('q', nextQuery);

    const nextSearchField = options?.searchField ?? getActiveSearchField();
    if (nextSearchField && nextSearchField !== 'all_fields') {
      newParams.set('search_field', nextSearchField);
    }

    // ALWAYS check URL params first for geo filters (source of truth)
    // This ensures geo filters are preserved even if component state is out of sync
    const geoType = searchParams.get('include_filters[geo][type]');
    if (geoType === 'bbox') {
      const topLeftLat = searchParams.get(
        'include_filters[geo][top_left][lat]'
      );
      const topLeftLon = searchParams.get(
        'include_filters[geo][top_left][lon]'
      );
      const bottomRightLat = searchParams.get(
        'include_filters[geo][bottom_right][lat]'
      );
      const bottomRightLon = searchParams.get(
        'include_filters[geo][bottom_right][lon]'
      );

      if (topLeftLat && topLeftLon && bottomRightLat && bottomRightLon) {
        setGeoBBoxParams(
          newParams,
          {
            topLeftLat,
            topLeftLon,
            bottomRightLat,
            bottomRightLon,
          },
          getGeoRelationFromParams()
        );
      }
    } else if (selectedPlace) {
      // Fallback to component state if URL params don't have geo filters but we have a selected place
      const attrs = selectedPlace.attributes;
      setGeoBBoxParams(newParams, {
        topLeftLat: attrs.max_latitude.toString(),
        topLeftLon: attrs.min_longitude.toString(),
        bottomRightLat: attrs.min_latitude.toString(),
        bottomRightLon: attrs.max_longitude.toString(),
      });
    }

    // Preserve category filters from current URL
    const categoryFilters = searchParams.getAll(
      'include_filters[gbl_resourceClass_sm][]'
    );
    const legacyCategoryFilters = searchParams.getAll(
      'fq[gbl_resourceClass_sm][]'
    );

    if (categoryFilters.length > 0) {
      categoryFilters.forEach((value) => {
        newParams.append('include_filters[gbl_resourceClass_sm][]', value);
      });
    } else if (legacyCategoryFilters.length > 0) {
      legacyCategoryFilters.forEach((value) => {
        newParams.append('include_filters[gbl_resourceClass_sm][]', value);
      });
    }

    return newParams;
  };

  const runKeywordSearch = (
    nextQuery: string,
    options?: { searchField?: string }
  ) => {
    const newParams = buildSearchNavigationParams(nextQuery, options);
    navigate(`/search?${newParams.toString()}`);
    setShowSuggestions(false);
  };

  const keepSuggestionClickActive = (e: React.MouseEvent) => {
    e.preventDefault();
  };

  const renderSuggestionText = (text: string) => {
    const trimmedQuery = query.trim().toLowerCase();
    if (!trimmedQuery || !text.toLowerCase().startsWith(trimmedQuery)) {
      return <span>{text}</span>;
    }

    const suffix = text.slice(trimmedQuery.length);
    if (!suffix) {
      return <span>{text}</span>;
    }

    return (
      <>
        <span>{text.slice(0, trimmedQuery.length)}</span>
        <span className="font-semibold">{suffix}</span>
      </>
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Handle keyboard navigation for keyword suggestions
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) =>
        prev < keywordMenuItems.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > -1 ? prev - 1 : -1));
    } else if (e.key === 'Enter') {
      // Always handle Enter in keyword input: prevent native form submit (which can cause
      // full-page navigation to current URL and leave user on homepage). Either run
      // suggestion navigation or trigger our submit handler via requestSubmit().
      if (selectedIndex >= 0) {
        e.preventDefault();
        const selectedItem = keywordMenuItems[selectedIndex];
        if (selectedItem.kind === 'scope') {
          runKeywordSearch(query.trim(), {
            searchField: selectedItem.searchField,
          });
        } else if (selectedItem.kind === 'suggestion') {
          runKeywordSearch(selectedItem.suggestion.text);
        } else if (selectedItem.kind === 'place') {
          handleSelectPlace(selectedItem.place);
        } else if (selectedItem.kind === 'place_loading') {
          return;
        } else {
          runKeywordSearch(query.trim(), { searchField: 'all_fields' });
        }
      } else {
        e.preventDefault();
        inputRef.current?.form?.requestSubmit();
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleAdvancedSearchClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (onAdvancedSearchClick) {
      onAdvancedSearchClick();
    } else {
      // Default behavior: navigate to search page and toggle advanced search
      const currentQuery = query.trim();
      const newParams = new URLSearchParams(searchParams);

      // Check if we're on search page and toggle accordingly
      if (window.location.pathname === '/search') {
        const currentShowAdvanced = newParams.get('showAdvanced') === 'true';
        if (currentShowAdvanced) {
          newParams.delete('showAdvanced');
        } else {
          newParams.set('showAdvanced', 'true');
        }
      } else {
        newParams.set('showAdvanced', 'true');
      }

      if (currentQuery) {
        newParams.set('q', currentQuery);
      }

      navigate(`/search?${newParams.toString()}`);
    }
  };

  const isAdvancedSearchOpen = searchParams.get('showAdvanced') === 'true';
  const hasGeoFilter =
    searchParams.get('include_filters[geo][type]') === 'bbox';
  const locationFilterLabel = selectedPlace
    ? selectedPlace.attributes.name || selectedPlace.attributes.display_name
    : hasGeoFilter
      ? 'Custom area'
      : null;
  const canClearPlace = selectedPlace !== null || hasGeoFilter;
  const activeSearchField = getActiveSearchField();
  const activeSearchFieldLabel =
    activeSearchField === 'dct_title_s'
      ? 'Title only'
      : activeSearchField === 'dct_subject_sm,dcat_theme_sm'
        ? 'Subject/Theme'
        : null;

  const trimmedQuery = query.trim();
  const placeLoadingItems: KeywordSuggestionItem[] =
    isLoadingPlaces && placeSuggestions.length === 0
      ? [{ kind: 'place_loading', id: 'place-loading' }]
      : [];
  const keywordMenuItems: KeywordSuggestionItem[] = trimmedQuery
    ? [
        ...suggestions.map((suggestion) => ({
          kind: 'suggestion' as const,
          id: `suggestion-${suggestion.text}`,
          suggestion,
        })),
        ...SCOPED_SEARCH_OPTIONS,
        ...placeLoadingItems,
        ...placeSuggestions.map((place) => ({
          kind: 'place' as const,
          id: `place-${place.id}`,
          place,
        })),
        { kind: 'see_all' as const, id: 'see-all' },
      ]
    : [];

  const getKeywordSuggestionGroup = (
    item: KeywordSuggestionItem
  ): KeywordSuggestionGroup => {
    if (item.kind === 'scope') return 'scope';
    if (item.kind === 'place' || item.kind === 'place_loading') return 'place';
    if (item.kind === 'suggestion') return 'suggestion';
    return 'see_all';
  };

  const getKeywordSuggestionHeading = (group: KeywordSuggestionGroup) => {
    if (group === 'scope') return 'Search only in';
    if (group === 'place') return 'Geographic Areas';
    if (group === 'suggestion') return 'Suggestions';
    return null;
  };

  const renderKeywordSuggestionHeading = (
    heading: string,
    group: KeywordSuggestionGroup,
    className: string
  ) => (
    <div className={className}>
      <span>{heading}</span>
      {group === 'place' && (
        <span className="ml-2 normal-case tracking-normal text-gray-400">
          Via OpenStreetMap
        </span>
      )}
    </div>
  );

  return (
    <div className="relative">
      <form
        onSubmit={handleSubmit}
        className="relative"
        role="search"
        aria-label="Search"
      >
        <div className="flex w-full items-stretch rounded-lg border border-gray-300 bg-white shadow-sm">
          <div className="relative min-w-0 flex-1">
            <div
              className={`flex h-full items-center gap-2 rounded-l-lg px-3 py-2.5 ${
                isKeywordInputFocused ? 'ring-2 ring-blue-500 ring-inset' : ''
              }`}
            >
              <Search
                className="h-4 w-4 shrink-0 text-gray-400"
                aria-hidden="true"
              />
              <input
                ref={inputRef}
                type="search"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShowSuggestions(true);
                  setSelectedIndex(-1);
                }}
                onFocus={() => {
                  setIsKeywordInputFocused(true);
                  if (
                    query.trim() ||
                    suggestions.length > 0 ||
                    placeSuggestions.length > 0
                  ) {
                    setShowSuggestions(true);
                  }
                }}
                onBlur={() => {
                  setIsKeywordInputFocused(false);
                  setTimeout(() => {
                    if (
                      !suggestionsRef.current?.contains(document.activeElement)
                    ) {
                      setShowSuggestions(false);
                    }
                  }, 200);
                }}
                onKeyDown={handleKeyDown}
                placeholder={responsivePlaceholder}
                autoFocus={autoFocus}
                aria-label="Search input"
                aria-describedby="search-description"
                className="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm font-medium text-gray-900 placeholder:text-gray-400 focus:outline-none"
              />
              {activeSearchFieldLabel && (
                <button
                  type="button"
                  onClick={handleClearSearchField}
                  className="hidden shrink-0 items-center gap-1 px-1 text-xs font-medium text-gray-500 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 lg:inline-flex"
                  aria-label={`Clear fielded search: ${activeSearchFieldLabel}`}
                  title={`Clear fielded search: ${activeSearchFieldLabel}`}
                >
                  <X className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {activeSearchFieldLabel}
                </button>
              )}
              {canClearPlace && locationFilterLabel && (
                <button
                  type="button"
                  onClick={handleClearPlace}
                  className="inline-flex max-w-[10rem] shrink-0 items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  aria-label={`Clear location filter: ${locationFilterLabel}`}
                  title={`Location filter: ${locationFilterLabel}`}
                >
                  <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span className="hidden truncate sm:inline">
                    {locationFilterLabel}
                  </span>
                  <X className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                </button>
              )}
            </div>

            {showSuggestions && keywordMenuItems.length > 0 && (
              <div
                ref={suggestionsRef}
                className="absolute left-0 right-0 top-[calc(100%+0.25rem)] z-10 max-h-96 overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg"
              >
                <div className="py-1">
                  {keywordMenuItems.map((item, index) => {
                    const isSelected = index === selectedIndex;
                    const group = getKeywordSuggestionGroup(item);
                    const previousGroup =
                      index > 0
                        ? getKeywordSuggestionGroup(keywordMenuItems[index - 1])
                        : null;
                    const heading =
                      group !== previousGroup
                        ? getKeywordSuggestionHeading(group)
                        : null;
                    const baseClass = `w-full px-4 py-2 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                      isSelected ? 'bg-gray-50' : ''
                    }`;

                    if (item.kind === 'scope') {
                      return (
                        <div key={item.id}>
                          {heading && (
                            <div
                              className={`px-4 pb-1 text-xs font-medium uppercase tracking-wide text-gray-500 ${
                                index === 0 ? 'pt-1' : 'pt-3'
                              }`}
                            >
                              {heading}
                            </div>
                          )}
                          <button
                            type="button"
                            className={baseClass}
                            onMouseDown={keepSuggestionClickActive}
                            onClick={() =>
                              runKeywordSearch(trimmedQuery, {
                                searchField: item.searchField,
                              })
                            }
                            onMouseEnter={() => setSelectedIndex(index)}
                          >
                            <div className="text-sm text-gray-700">
                              <span>{trimmedQuery}</span>{' '}
                              <span className="text-gray-500">in</span>{' '}
                              <span className="font-medium text-gray-900">
                                {item.label}
                              </span>
                            </div>
                          </button>
                        </div>
                      );
                    }

                    if (item.kind === 'place_loading') {
                      return (
                        <div key={item.id}>
                          {heading &&
                            renderKeywordSuggestionHeading(
                              heading,
                              group,
                              'px-4 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-gray-500'
                            )}
                          <div className="px-4 py-2 text-sm text-gray-500">
                            Searching places...
                          </div>
                        </div>
                      );
                    }

                    if (item.kind === 'place') {
                      const attrs = item.place.attributes;
                      const placeName = attrs.name || attrs.display_name;
                      const placeTypeLabel = formatPlaceTypeLabel(
                        attrs.placetype
                      );

                      return (
                        <div key={item.id}>
                          {heading &&
                            renderKeywordSuggestionHeading(
                              heading,
                              group,
                              'px-4 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-gray-500'
                            )}
                          <button
                            type="button"
                            className={baseClass}
                            onMouseDown={keepSuggestionClickActive}
                            onClick={() => handleSelectPlace(item.place)}
                            onMouseEnter={() => setSelectedIndex(index)}
                          >
                            <div className="flex items-start gap-2">
                              <MapPin
                                className="mt-0.5 h-4 w-4 shrink-0 text-gray-400"
                                aria-hidden="true"
                              />
                              <div className="min-w-0">
                                <div className="text-sm text-gray-900">
                                  <span className="font-medium">
                                    {placeName}
                                  </span>{' '}
                                  {placeTypeLabel && (
                                    <span className="text-gray-500">
                                      ({placeTypeLabel})
                                    </span>
                                  )}
                                </div>
                                <div className="truncate text-xs text-gray-500">
                                  {attrs.display_name || placeName}
                                </div>
                              </div>
                            </div>
                          </button>
                        </div>
                      );
                    }

                    if (item.kind === 'see_all') {
                      return (
                        <button
                          key={item.id}
                          type="button"
                          className={`${baseClass} mt-1 border-t border-gray-200 pt-3`}
                          onMouseDown={keepSuggestionClickActive}
                          onClick={() =>
                            runKeywordSearch(trimmedQuery, {
                              searchField: 'all_fields',
                            })
                          }
                          onMouseEnter={() => setSelectedIndex(index)}
                        >
                          <div className="text-sm font-medium text-gray-800">
                            See all results for{' '}
                            <span className="text-blue-700 underline underline-offset-2">
                              {trimmedQuery}
                            </span>
                          </div>
                        </button>
                      );
                    }

                    return (
                      <div key={item.id}>
                        {heading && (
                          <div className="px-4 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-gray-500">
                            {heading}
                          </div>
                        )}
                        <button
                          type="button"
                          className={baseClass}
                          onMouseDown={keepSuggestionClickActive}
                          onClick={() => runKeywordSearch(item.suggestion.text)}
                          onMouseEnter={() => setSelectedIndex(index)}
                        >
                          <div className="text-sm text-gray-900">
                            {renderSuggestionText(item.suggestion.text)}
                          </div>
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="flex shrink-0 items-center p-1">
            <div className="inline-flex overflow-hidden rounded-md bg-brand text-white">
              <button
                type="submit"
                className="inline-flex items-center px-3 py-3 text-sm font-medium transition-colors hover:bg-brand/90 focus:outline-none focus:ring-2 focus:ring-white/70 focus:ring-inset sm:px-4"
                aria-label="Submit search"
              >
                <span>Search</span>
              </button>

              {showAdvancedButton && (
                <button
                  type="button"
                  onClick={handleAdvancedSearchClick}
                  className={`inline-flex items-center border-l border-white/20 px-3 py-3 transition-colors focus:outline-none focus:ring-2 focus:ring-white/70 focus:ring-inset ${
                    isAdvancedSearchOpen
                      ? 'bg-brand/80 hover:bg-brand/75'
                      : 'hover:bg-brand/90'
                  }`}
                  aria-label={
                    isAdvancedSearchOpen
                      ? 'Hide advanced search'
                      : 'Advanced search'
                  }
                  title="Advanced search"
                >
                  <Settings className="h-4 w-4" aria-hidden="true" />
                  <span className="sr-only">
                    {isAdvancedSearchOpen
                      ? 'Hide advanced search'
                      : 'Advanced search'}
                  </span>
                </button>
              )}
            </div>
          </div>
        </div>

        <span id="search-description" className="sr-only">
          Press Enter or click the search button to submit your search
        </span>
      </form>
    </div>
  );
}
