import React, { useState, useEffect, useRef } from 'react';
import { Search, Settings, X, MapPin } from 'lucide-react';
import { fetchNominatimSearch } from '../services/api';
import { useNavigate, useSearchParams } from 'react-router';
import type { GazetteerPlace } from '../types/api';

interface SearchFieldProps {
  onSearch?: (query: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  showAdvancedButton?: boolean;
  onAdvancedSearchClick?: () => void;
}

export function SearchField({
  onSearch: _onSearch, // eslint-disable-line @typescript-eslint/no-unused-vars
  placeholder = 'Search...',
  autoFocus,
  showAdvancedButton = false,
  onAdvancedSearchClick,
}: SearchFieldProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<
    Array<{ text: string; title: string }>
  >([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Placename autocomplete state
  const [selectedPlace, setSelectedPlace] = useState<GazetteerPlace | null>(
    null
  );
  const [placeQuery, setPlaceQuery] = useState('');
  const [placeSuggestions, setPlaceSuggestions] = useState<GazetteerPlace[]>(
    []
  );
  const [showPlaceSuggestions, setShowPlaceSuggestions] = useState(false);
  const [placeSelectedIndex, setPlaceSelectedIndex] = useState(-1);
  const [isLoadingPlaces, setIsLoadingPlaces] = useState(false);
  const placeInputRef = useRef<HTMLInputElement>(null);
  const placeSuggestionsRef = useRef<HTMLDivElement>(null);
  const [isPlaceInputFocused, setIsPlaceInputFocused] = useState(false);
  const [isKeywordInputFocused, setIsKeywordInputFocused] = useState(false);

  // Sync query with URL params (e.g., when Clear All is clicked)
  useEffect(() => {
    const urlQuery = searchParams.get('q') || '';
    // Only update if the URL value is different from current state
    // This handles cases where Clear All removes the 'q' param
    // Note: We don't include 'query' in deps to avoid resetting while user types
    if (urlQuery !== query) {
      setQuery(urlQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]); // Watch for URL param changes only

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
    const fetchSuggestionsDebounced = setTimeout(async () => {
      if (query.trim() && !isPlaceInputFocused) {
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
          const data = Array.isArray(json?.data) ? json.data : [];
          setSuggestions(
            data.map((r: any) => ({
              text: r?.attributes?.text ?? '',
              title: r?.attributes?.title ?? '',
            }))
          );
        } catch (error) {
          console.error('Error fetching keyword suggestions:', error);
          setSuggestions([]);
        }
      } else {
        setSuggestions([]);
      }
    }, 300);

    return () => clearTimeout(fetchSuggestionsDebounced);
  }, [query, isPlaceInputFocused]);

  // Fetch placename suggestions
  useEffect(() => {
    const fetchPlaceSuggestionsDebounced = setTimeout(async () => {
      if (placeQuery.trim() && isPlaceInputFocused) {
        setIsLoadingPlaces(true);
        try {
          const response = await fetchNominatimSearch(placeQuery.trim(), 10);
          setPlaceSuggestions(response.data || []);
        } catch (error) {
          console.error('Error fetching placename suggestions:', error);
          setPlaceSuggestions([]);
        } finally {
          setIsLoadingPlaces(false);
        }
      } else {
        setPlaceSuggestions([]);
      }
    }, 500); // Longer debounce for Nominatim rate limiting

    return () => clearTimeout(fetchPlaceSuggestionsDebounced);
  }, [placeQuery, isPlaceInputFocused]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(target) &&
        !inputRef.current?.contains(target) &&
        placeSuggestionsRef.current &&
        !placeSuggestionsRef.current.contains(target) &&
        !placeInputRef.current?.contains(target)
      ) {
        setShowSuggestions(false);
        setShowPlaceSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectPlace = (place: GazetteerPlace) => {
    const attrs = place.attributes;

    // Debug: Log the place and bbox values
    console.log('📍 Selected place:', {
      name: attrs.name,
      placetype: attrs.placetype,
      min_latitude: attrs.min_latitude,
      max_latitude: attrs.max_latitude,
      min_longitude: attrs.min_longitude,
      max_longitude: attrs.max_longitude,
    });

    setSelectedPlace(place);
    setPlaceQuery('');
    setShowPlaceSuggestions(false);
    setIsPlaceInputFocused(false);

    // Create bbox from min/max lat/lng
    const newParams = new URLSearchParams(searchParams);

    // Preserve keyword query if present
    const currentQuery = query.trim() || searchParams.get('q') || '';
    if (currentQuery) {
      newParams.set('q', currentQuery);
    }

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

    console.log('🗺️ Setting bbox:', {
      top_left: { lat: topLeftLat, lon: topLeftLon },
      bottom_right: { lat: bottomRightLat, lon: bottomRightLon },
    });

    newParams.set('include_filters[geo][type]', 'bbox');
    newParams.set('include_filters[geo][field]', 'dcat_bbox');
    newParams.set('include_filters[geo][top_left][lat]', topLeftLat.toString());
    newParams.set('include_filters[geo][top_left][lon]', topLeftLon.toString());
    newParams.set(
      'include_filters[geo][bottom_right][lat]',
      bottomRightLat.toString()
    );
    newParams.set(
      'include_filters[geo][bottom_right][lon]',
      bottomRightLon.toString()
    );

    // Preserve category filters
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

    // Reset to page 1 when bbox changes
    newParams.delete('page');

    // Update URL params without navigating (this prevents auto-submit)
    // The search will only happen when the user explicitly submits the form
    setSearchParams(newParams);

    // Focus back on keyword input so user can enter their search query
    // Use setTimeout to ensure state updates complete before focusing
    setTimeout(() => {
      inputRef.current?.focus();
    }, 0);
  };

  const handleClearPlace = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedPlace(null);
    setPlaceQuery('');
    setShowPlaceSuggestions(false);

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

    // Preserve category filters
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

    newParams.delete('page');

    // Navigate to update URL
    navigate(`/search?${newParams.toString()}`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newParams = new URLSearchParams();

    // Always add keyword query if present (from input state)
    if (query.trim()) {
      newParams.set('q', query.trim());
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
        newParams.set('include_filters[geo][type]', 'bbox');
        newParams.set('include_filters[geo][field]', 'dcat_bbox');
        newParams.set('include_filters[geo][top_left][lat]', topLeftLat);
        newParams.set('include_filters[geo][top_left][lon]', topLeftLon);
        newParams.set(
          'include_filters[geo][bottom_right][lat]',
          bottomRightLat
        );
        newParams.set(
          'include_filters[geo][bottom_right][lon]',
          bottomRightLon
        );
      }
    } else if (selectedPlace) {
      // Fallback to component state if URL params don't have geo filters but we have a selected place
      const attrs = selectedPlace.attributes;
      newParams.set('include_filters[geo][type]', 'bbox');
      newParams.set('include_filters[geo][field]', 'dcat_bbox');
      newParams.set(
        'include_filters[geo][top_left][lat]',
        attrs.max_latitude.toString()
      );
      newParams.set(
        'include_filters[geo][top_left][lon]',
        attrs.min_longitude.toString()
      );
      newParams.set(
        'include_filters[geo][bottom_right][lat]',
        attrs.min_latitude.toString()
      );
      newParams.set(
        'include_filters[geo][bottom_right][lon]',
        attrs.max_longitude.toString()
      );
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

    // Only navigate if we have at least a query or geo filters
    if (query.trim() || geoType === 'bbox' || selectedPlace) {
      navigate(`/search?${newParams.toString()}`);
      setShowSuggestions(false);
      setShowPlaceSuggestions(false);
      // Don't call onSearch callback here - we're handling navigation ourselves
      // The callback would cause a second navigation that could override our params
    }
  };

  const handlePlaceKeyDown = (e: React.KeyboardEvent) => {
    // Handle keyboard navigation for place suggestions
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setPlaceSelectedIndex((prev) =>
        prev < placeSuggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setPlaceSelectedIndex((prev) => (prev > -1 ? prev - 1 : -1));
    } else if (e.key === 'Enter') {
      e.preventDefault(); // Always prevent form submission from place input
      if (placeSelectedIndex >= 0) {
        // Select the highlighted suggestion
        handleSelectPlace(placeSuggestions[placeSelectedIndex]);
      } else {
        // No suggestion selected - just move focus to keyword input
        setIsPlaceInputFocused(false);
        inputRef.current?.focus();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setShowPlaceSuggestions(false);
      setIsPlaceInputFocused(false);
      inputRef.current?.focus();
    } else if (e.key === 'Tab' && !e.shiftKey) {
      // Allow tab to move to keyword input
      setIsPlaceInputFocused(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Handle keyboard navigation for keyword suggestions
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) =>
        prev < suggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > -1 ? prev - 1 : -1));
    } else if (e.key === 'Tab' && e.shiftKey) {
      // Back-tab: move focus to place input for accessibility
      e.preventDefault();
      setIsKeywordInputFocused(false);
      setIsPlaceInputFocused(true);
      setPlaceQuery('');
      setTimeout(() => {
        placeInputRef.current?.focus();
      }, 0);
    } else if (e.key === 'Enter') {
      // Always handle Enter in keyword input: prevent native form submit (which can cause
      // full-page navigation to current URL and leave user on homepage). Either run
      // suggestion navigation or trigger our submit handler via requestSubmit().
      if (selectedIndex >= 0) {
        e.preventDefault();
        const suggestion = suggestions[selectedIndex];
        const newParams = new URLSearchParams();
        newParams.set('q', suggestion.text);

        // Preserve geo filters if place is selected
        if (selectedPlace) {
          const attrs = selectedPlace.attributes;
          newParams.set('include_filters[geo][type]', 'bbox');
          newParams.set('include_filters[geo][field]', 'dcat_bbox');
          newParams.set(
            'include_filters[geo][top_left][lat]',
            attrs.max_latitude.toString()
          );
          newParams.set(
            'include_filters[geo][top_left][lon]',
            attrs.min_longitude.toString()
          );
          newParams.set(
            'include_filters[geo][bottom_right][lat]',
            attrs.min_latitude.toString()
          );
          newParams.set(
            'include_filters[geo][bottom_right][lon]',
            attrs.max_longitude.toString()
          );
        } else {
          // Also check URL params for geo filters (in case place was set but component state wasn't updated)
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
              newParams.set('include_filters[geo][type]', 'bbox');
              newParams.set('include_filters[geo][field]', 'dcat_bbox');
              newParams.set('include_filters[geo][top_left][lat]', topLeftLat);
              newParams.set('include_filters[geo][top_left][lon]', topLeftLon);
              newParams.set(
                'include_filters[geo][bottom_right][lat]',
                bottomRightLat
              );
              newParams.set(
                'include_filters[geo][bottom_right][lon]',
                bottomRightLon
              );
            }
          }
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

        navigate(`/search?${newParams.toString()}`);
        setShowSuggestions(false);
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

  const rightPadding = showAdvancedButton ? 'pr-32' : 'pr-24';

  // Determine place name to display
  const hasGeoFilter =
    searchParams.get('include_filters[geo][type]') === 'bbox';
  const placeDisplayValue = selectedPlace
    ? selectedPlace.attributes.name || selectedPlace.attributes.display_name
    : hasGeoFilter
      ? 'Location filtered'
      : 'Everywhere';

  // Check if either input is focused
  const isAnyInputFocused = isPlaceInputFocused || isKeywordInputFocused;

  return (
    <div className="relative">
      <form
        onSubmit={handleSubmit}
        className="relative"
        role="search"
        aria-label="Search"
      >
        <div
          className={`flex items-center gap-0 rounded-lg transition-all ${
            isAnyInputFocused ? 'ring-2 ring-blue-500 ring-offset-0' : ''
          }`}
        >
          {/* Place input (left side) */}
          <div className="relative">
            {isPlaceInputFocused ? (
              <>
                <input
                  ref={placeInputRef}
                  type="text"
                  value={placeQuery}
                  onChange={(e) => {
                    setPlaceQuery(e.target.value);
                    setShowPlaceSuggestions(true);
                    setPlaceSelectedIndex(-1);
                  }}
                  onFocus={() => {
                    setIsPlaceInputFocused(true);
                    setIsKeywordInputFocused(false);
                    if (placeQuery.trim() || placeSuggestions.length > 0) {
                      setShowPlaceSuggestions(true);
                    }
                  }}
                  onBlur={() => {
                    // Delay to allow click events on suggestions
                    setTimeout(() => {
                      if (
                        !placeSuggestionsRef.current?.contains(
                          document.activeElement
                        )
                      ) {
                        setIsPlaceInputFocused(false);
                        setShowPlaceSuggestions(false);
                        if (!placeQuery.trim() && !selectedPlace) {
                          setPlaceQuery('');
                        }
                      }
                    }, 200);
                  }}
                  onKeyDown={handlePlaceKeyDown}
                  placeholder="Search for a place..."
                  className="w-[180px] pl-8 pr-3 py-2 text-gray-900 placeholder-gray-500 border border-r-0 border-gray-300 rounded-l-lg focus:outline-none focus:z-10"
                />
                <div className="absolute inset-y-0 left-0 flex items-center pl-2.5 pointer-events-none">
                  <MapPin
                    className="w-4 h-4 text-gray-400"
                    aria-hidden="true"
                  />
                </div>
              </>
            ) : (
              <div className="relative w-[180px]">
                <button
                  type="button"
                  onClick={() => {
                    setIsPlaceInputFocused(true);
                    setPlaceQuery('');
                    setShowPlaceSuggestions(false);
                    setTimeout(() => placeInputRef.current?.focus(), 0);
                  }}
                  onFocus={() => {
                    // When button receives focus (e.g., via Shift+Tab), switch to input mode
                    setIsPlaceInputFocused(true);
                    setPlaceQuery('');
                    setShowPlaceSuggestions(false);
                    setTimeout(() => placeInputRef.current?.focus(), 0);
                  }}
                  className={`w-full px-3 py-2 pl-8 pr-8 font-medium text-left border border-r-0 border-gray-300 rounded-l-lg bg-white hover:bg-gray-50 focus:outline-none focus:z-10 transition-colors ${
                    selectedPlace ? 'text-blue-700' : 'text-gray-700'
                  }`}
                  aria-label="Select location"
                >
                  <div className="absolute inset-y-0 left-0 flex items-center pl-2.5 pointer-events-none">
                    <MapPin
                      className="w-4 h-4 text-gray-400"
                      aria-hidden="true"
                    />
                  </div>
                  <span className="truncate block">{placeDisplayValue}</span>
                </button>
                {selectedPlace && (
                  <button
                    type="button"
                    onClick={handleClearPlace}
                    className="absolute inset-y-0 right-0 flex items-center pr-2 text-gray-400 hover:text-gray-600 focus:outline-none z-10"
                    aria-label="Clear location"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Keyword search input (right side) */}
          <div className="relative flex-1">
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
                setIsPlaceInputFocused(false);
                setIsKeywordInputFocused(true);
                if (suggestions.length > 0) {
                  setShowSuggestions(true);
                }
              }}
              onBlur={() => {
                setIsKeywordInputFocused(false);
                // Close suggestions when focus leaves the input
                // Delay to allow click events on suggestions
                setTimeout(() => {
                  if (
                    !suggestionsRef.current?.contains(document.activeElement)
                  ) {
                    setShowSuggestions(false);
                  }
                }, 200);
              }}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              autoFocus={autoFocus}
              aria-label="Search input"
              aria-describedby="search-description"
              className={`w-full px-4 py-2 pl-10 ${rightPadding} text-gray-900 placeholder-gray-500 border border-gray-300 rounded-r-lg focus:outline-none`}
            />
            <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
              <Search className="w-5 h-5 text-gray-400" aria-hidden="true" />
            </div>
          </div>
        </div>

        {showAdvancedButton && (
          <button
            type="button"
            onClick={handleAdvancedSearchClick}
            className="absolute inset-y-0 right-24 flex items-center pr-3 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset"
            aria-label="Advanced search"
            title="Advanced search"
          >
            <Settings className="w-5 h-5" aria-hidden="true" />
          </button>
        )}
        <button
          type="submit"
          className={`absolute inset-y-1 ${showAdvancedButton ? 'right-1' : 'right-1'} flex items-center px-4 py-1.5 text-sm font-medium text-white bg-brand hover:bg-brand/90 rounded-md focus:outline-none focus:ring-2 focus:ring-white/70 focus:ring-offset-2 transition-colors`}
          aria-label="Submit search"
        >
          Search
        </button>
        <span id="search-description" className="sr-only">
          Press Enter or click the search button to submit your search
        </span>
      </form>

      {/* Place suggestions dropdown */}
      {showPlaceSuggestions &&
        (placeSuggestions.length > 0 || isLoadingPlaces) &&
        isPlaceInputFocused && (
          <div
            ref={placeSuggestionsRef}
            className="absolute z-20 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-64 overflow-auto"
          >
            {isLoadingPlaces ? (
              <div className="px-4 py-2 text-sm text-gray-500">
                Searching...
              </div>
            ) : placeSuggestions.length === 0 ? (
              <div className="px-4 py-2 text-sm text-gray-500">
                No places found
              </div>
            ) : (
              placeSuggestions.map((place, index) => (
                <button
                  key={place.id}
                  className={`w-full text-left px-4 py-2 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                    index === placeSelectedIndex ? 'bg-gray-50' : ''
                  }`}
                  onClick={() => handleSelectPlace(place)}
                  onMouseEnter={() => setPlaceSelectedIndex(index)}
                >
                  <div className="text-sm text-gray-900 font-medium">
                    {place.attributes.name}{' '}
                    {place.attributes.placetype &&
                      `(${place.attributes.placetype})`}
                  </div>
                  <div className="text-xs text-gray-500">
                    {place.attributes.display_name || place.attributes.name}
                  </div>
                </button>
              ))
            )}
          </div>
        )}

      {/* Keyword suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && !isPlaceInputFocused && (
        <div
          ref={suggestionsRef}
          className="absolute z-10 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-96 overflow-auto"
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              className={`w-full text-left px-4 py-2 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                index === selectedIndex ? 'bg-gray-50' : ''
              }`}
              onClick={() => {
                const newParams = new URLSearchParams();
                newParams.set('q', suggestion.text);

                // Preserve geo filters if place is selected
                if (selectedPlace) {
                  const attrs = selectedPlace.attributes;
                  newParams.set('include_filters[geo][type]', 'bbox');
                  newParams.set('include_filters[geo][field]', 'dcat_bbox');
                  newParams.set(
                    'include_filters[geo][top_left][lat]',
                    attrs.max_latitude.toString()
                  );
                  newParams.set(
                    'include_filters[geo][top_left][lon]',
                    attrs.min_longitude.toString()
                  );
                  newParams.set(
                    'include_filters[geo][bottom_right][lat]',
                    attrs.min_latitude.toString()
                  );
                  newParams.set(
                    'include_filters[geo][bottom_right][lon]',
                    attrs.max_longitude.toString()
                  );
                } else {
                  // Also check URL params for geo filters (in case place was set but component state wasn't updated)
                  const geoType = searchParams.get(
                    'include_filters[geo][type]'
                  );
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

                    if (
                      topLeftLat &&
                      topLeftLon &&
                      bottomRightLat &&
                      bottomRightLon
                    ) {
                      newParams.set('include_filters[geo][type]', 'bbox');
                      newParams.set('include_filters[geo][field]', 'dcat_bbox');
                      newParams.set(
                        'include_filters[geo][top_left][lat]',
                        topLeftLat
                      );
                      newParams.set(
                        'include_filters[geo][top_left][lon]',
                        topLeftLon
                      );
                      newParams.set(
                        'include_filters[geo][bottom_right][lat]',
                        bottomRightLat
                      );
                      newParams.set(
                        'include_filters[geo][bottom_right][lon]',
                        bottomRightLon
                      );
                    }
                  }
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
                    newParams.append(
                      'include_filters[gbl_resourceClass_sm][]',
                      value
                    );
                  });
                } else if (legacyCategoryFilters.length > 0) {
                  legacyCategoryFilters.forEach((value) => {
                    newParams.append(
                      'include_filters[gbl_resourceClass_sm][]',
                      value
                    );
                  });
                }

                navigate(`/search?${newParams.toString()}`);
                setShowSuggestions(false);
              }}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <div className="text-sm text-gray-900">{suggestion.text}</div>
              {suggestion.text !== suggestion.title && (
                <div className="text-xs text-gray-500 truncate">
                  {suggestion.title}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
