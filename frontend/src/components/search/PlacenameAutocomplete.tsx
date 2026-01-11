import React, { useState, useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { fetchNominatimSearch } from '../../services/api';
import { useSearchParams } from 'react-router';
import type { GazetteerPlace } from '../../types/api';

interface PlacenameAutocompleteProps {
  onSelect?: (place: GazetteerPlace) => void;
  onPlaceSelect?: (place: GazetteerPlace) => void;
}

export function PlacenameAutocomplete({
  onSelect,
  onPlaceSelect,
}: PlacenameAutocompleteProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<GazetteerPlace[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const fetchSuggestionsDebounced = setTimeout(async () => {
      if (query.trim()) {
        setIsLoading(true);
        try {
          const response = await fetchNominatimSearch(query.trim(), 10);
          setSuggestions(response.data || []);
        } catch (error) {
          console.error('Error fetching placename suggestions:', error);
          setSuggestions([]);
        } finally {
          setIsLoading(false);
        }
      } else {
        setSuggestions([]);
      }
    }, 500); // Slightly longer debounce to respect rate limiting

    return () => clearTimeout(fetchSuggestionsDebounced);
  }, [query]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node) &&
        !inputRef.current?.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectPlace = (place: GazetteerPlace) => {
    const attrs = place.attributes;

    // Create bbox from min/max lat/lng
    // top_left is northwest (higher lat, lower lon)
    // bottom_right is southeast (lower lat, higher lon)
    const newParams = new URLSearchParams(searchParams);

    // Remove existing geo filters
    Array.from(newParams.keys())
      .filter((key) => key.startsWith('include_filters[geo]'))
      .forEach((key) => newParams.delete(key));

    // Add new bbox filter
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

    // Reset to page 1 when bbox changes
    newParams.delete('page');

    setSearchParams(newParams);

    // Call optional callbacks
    onSelect?.(place);
    onPlaceSelect?.(place);

    // Clear input and close dropdown
    setQuery('');
    setShowSuggestions(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) =>
        prev < suggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > -1 ? prev - 1 : -1));
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault();
      handleSelectPlace(suggestions[selectedIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  return (
    <div className="relative mb-2">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowSuggestions(true);
            setSelectedIndex(-1);
          }}
          onFocus={() => {
            if (suggestions.length > 0) {
              setShowSuggestions(true);
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search for a place..."
          aria-label="Search for a place"
          className="w-full px-4 py-2 pl-10 pr-10 text-sm text-gray-900 placeholder-gray-500 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
          <Search className="w-4 h-4 text-gray-400" aria-hidden="true" />
        </div>
        {isLoading && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
          </div>
        )}
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && (suggestions.length > 0 || isLoading) && (
        <div
          ref={suggestionsRef}
          className="absolute z-20 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-64 overflow-auto"
        >
          {isLoading ? (
            <div className="px-4 py-2 text-sm text-gray-500">Searching...</div>
          ) : suggestions.length === 0 ? (
            <div className="px-4 py-2 text-sm text-gray-500">
              No places found
            </div>
          ) : (
            suggestions.map((place, index) => (
              <button
                key={place.id}
                className={`w-full text-left px-4 py-2 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                  index === selectedIndex ? 'bg-gray-50' : ''
                }`}
                onClick={() => handleSelectPlace(place)}
                onMouseEnter={() => setSelectedIndex(index)}
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
    </div>
  );
}
